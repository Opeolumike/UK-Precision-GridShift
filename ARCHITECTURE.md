# Architecture and Geodetic Logic Document for UK Precision GridShift

**Prepared By:** Michael Opeoluwa

**Last Updated:** June 2026

**Purpose:** To explain the architecture, mathematical pipelines, and design logic for the UK Precision GridShift. This document serves as the reference for the geodetic transformations applied within the software, specifically defending the pipeline architecture against common PROJ library misconceptions.

---

## Part 1: System Initialisation and Failsafes

**Logic:** Before any pixels or points are moved, the software must verify the environment. Geodetic transformations fail silently if grid files are missing, falling back to lower-accuracy transformation methods. This software enforces strict validation up front.

```
START CLI ROUTING
    ACCEPT Arguments: Type of Data, Input Path, Output Path, Grid Folder Path

    MATCH Data Type:
        IF 'multi' -> Route to Multispectral Function
        IF 'ortho' -> Route to RGB Function
        IF 'dem'   -> Route to DSM/DTM Function
        IF 'las'   -> Route to Point Cloud Function

    CATCH Errors:
        If any step fails, terminate and print the exact error to the user.
END
```

---

## Part 2: 2D Planimetric Shifts (RGB & Multispectral)

**Logic:** For 2D raster datasets, only horizontal coordinate transformations are required. We use rasterio's internal warping engine tied strictly to the OSTN15 grid.

**Crucial Decision:** For multispectral and raw RGB data, Nearest Neighbour resampling is required to preserve original spectral reflectance values. Using bilinear or cubic interpolation would mathematically average the adjacent pixels, altering the original spectral reflectance values captured by the drone sensors.

**Crucial Decision — Locking Output Resolution to the Native Input GSD:** By default, `calculate_default_transform` computes its own output resolution for the destination CRS, based on the geometric distortion introduced by the reprojection itself. This default behaviour is not wrong, but it is not predictable from the user's perspective — the output pixel size can end up subtly larger or smaller than the original Ground Sample Distance (GSD) the drone actually captured, depending on the specific bounds and projection involved. For a tool whose stated purpose is preserving survey-grade precision, an unpredictable resolution drift undermines that claim even if the geodetic transformation itself is correct.

The fix is to read the input raster's own native resolution and pass it explicitly to `calculate_default_transform`, rather than letting GDAL choose:

```
DEFINE lock_output_resolution(input_raster):
    READ native_resolution = input_raster's own pixel size (src.res[0])
    PASS resolution=native_resolution into calculate_default_transform
    (Overrides GDAL's auto-calculated resolution with the exact input GSD)
```

This guarantees the reprojected output preserves the same pixel size as the original capture, rather than an auto-derived approximation. One practical consequence worth being aware of: because this changes the exact output pixel grid (and therefore the exact sub-pixel position of every feature in the image, including survey targets), any QA accuracy figures generated against an orthomosaic reprojected with this fix are not directly numerically comparable to QA figures generated before this change was introduced — both are internally consistent and valid, but they are evaluating the targets at a different underlying pixel grid.

```
DEFINE reproject_2D_raster(input, output, grids):

    STEP 1: Point the PyProj environment to the custom Grid Folder.

    STEP 2: File Validation Failsafe
        CHECK if "ostn15_etrs_to_osgb.gsb" exists.
        IF NOT: Halt program. (We do not allow fallback to low-precision Helmert math).

    STEP 3: Define the strict BNG Pipeline
        SET Base = Transverse Mercator, Airy Ellipsoid, False Origin (400k, -100k)
        SET Grid = Append OSTN15 horizontal shift to Base

    STEP 4: Raster Warping
        OPEN input WGS84 UTM Zone 30N raster
        CALCULATE the new bounding box and resolution for BNG
        CREATE an empty destination raster with these new dimensions

        FOR EACH spectral band in the raster:
            WARP pixels from WGS84 UTM Zone 30N to BNG using the OSTN15 pipeline
            ENFORCE Nearest Neighbour resampling to preserve raw spectral data

    STEP 5: SAVE and CLOSE.
```

---

## Part 3: The Raster Elevation Transformation (DSM AND DTM) & Geodetic Defense

### The Mathematics behind Vertical Transformation

To calculate accurate Ordnance Datum Newlyn (ODN) elevations from raw drone GPS data, we must define three variables:

- **h (Ellipsoidal Height):** The raw drone altitude (WGS84/ETRS89)
- **N (Geoid Undulation):** The gravitational offset between the WGS84 Ellipsoid and true sea level, stored in the OSGM15 grid
- **H (Orthometric Height):** True ODN ground elevation

The universal geodetic equation is:

h = H + N

To solve for the true ground height (H), the algebra requires subtraction:

H = h - N

### Default Behaviour of PROJ Vertical Grid Transformations and The +inv Solution

By default, the PROJ `+vgridshift` command adds the grid value:

Output = h + N

This would produce an incorrect result for the intended orthometric height conversion and produce substantial vertical offsets (typically tens of metres across Great Britain). To force the software to calculate `H = h - N`, we must pass the `+inv` (inverse) flag.

### Separation of Horizontal and Vertical Transformations

If we warp the X/Y coordinates into BNG, and then run a vertical PROJ pipeline that also contains horizontal shifts, we risk double-shifting the footprint.

**The Solution:** We separate the operations. We let Rasterio handle the planimetric X/Y warp. Then, we build a temporary PROJ pipeline that runs in reverse (`+inv`) solely to look up the correct geoid value, calculate the new height, and deliberately throw away the temporary X/Y data to protect the Rasterio footprint.

```
DEFINE reproject_dem_odn(input, output, grids):

    STEP 1: Validate both OSTN15 (Horizontal) and OSGM15 (Vertical) grid files.
            IF either is missing, aggregate the errors and HALT.

    STEP 2: Define the Z-Shift PROJ Pipeline
        PIPELINE =
            1. REVERSE BNG Eastings/Northings back to OSGB36 Lat/Lon  (+inv +proj=tmerc)
            2. REVERSE OSGB36 back to WGS84 Lat/Lon                   (+inv +proj=hgridshift)
            3. APPLY OSGM15 Geoid Undulation to get ODN Height         (+inv +proj=vgridshift)

    STEP 3: Planimetric Warp (The X/Y Shift)
        OPEN input WGS84 UTM Zone 30N DSM/DTM
        LOCK output resolution to the input's native pixel size, rather
            than letting GDAL auto-calculate it (see Part 2's note on
            Locking Output Resolution — the same principle applies here:
            elevation precision should not silently drift from the
            original capture resolution during reprojection).
        WARP from WGS84 UTM Zone 30N to BNG using OSTN15 (Rasterio handles the precise footprint)
        ENFORCE Bilinear resampling (Elevation is continuous; bilinear prevents terracing).
        SAVE to output.

    STEP 4: Vertical Shift (The Z Shift)
        OPEN the newly horizontally-shifted BNG raster
        READ data block-by-block (Prevents RAM overload on massive drone maps)

        FOR EACH valid pixel:
            GET its current BNG X and Y coordinate.
            PASS X, Y, and original GPS Z into the Z-Shift PROJ Pipeline.

            EXTRACT only the new Z value (z_odn).
            DISCARD the pipeline's output X and Y (Prevents the double-shift).

            OVERWRITE the pixel's old Z with z_odn.

    STEP 5: UPDATE metadata tags to declare VERTICAL_DATUM="ODN".
    STEP 6: SAVE and CLOSE.
```

---

## Part 4: 3D Vector Processing (LAS Point Clouds)

**Logic:** Unlike rasters, point clouds are discrete 3D vectors. We do not need Rasterio to warp a bounding box. We can pass the exact X, Y, and Z of every single laser return through a single, continuous PROJ 3D pipeline. We utilise NumPy array masking to process millions of coordinates efficiently within the CPU, rather than utilising highly inefficient for loops.

```
DEFINE reproject_point_cloud(input_folder, output_folder, grids):

    STEP 1: Validate both OSTN15 and OSGM15 grid files.

    STEP 2: Define the Continuous 3D Pipeline
        PIPELINE =
            1. REVERSE UTM Zone 30N back to raw WGS84      (+inv +proj=utm)
            2. SUBTRACT OSGM15 Geoid to get ODN Height     (+inv +proj=vgridshift)
            3. FORWARD shift WGS84 to OSGB36               (+proj=hgridshift OSTN15)
            4. FORWARD project to British National Grid     (+proj=tmerc)

    STEP 3: Batch Processing
        FIND all .las files in the input folder.

        FOR EACH file:
            READ points into RAM using LASpy.
            EXTRACT X, Y, Z arrays.

            TRANSFORM arrays simultaneously using NumPy and the PROJ pipeline.
            FILTER out any invalid or infinite points.

            CREATE a new LAS file structure.
            CALCULATE optimal offset and scale headers (essential for LAS precision).
            INJECT the new BNG/ODN coordinates.
            COPY over all extra drone data (RGB colours, intensity, classifications).

            SAVE file with "_BNG_ODN.las" suffix.
```

## Part 5: The Quality Assurance (QA) Engine

**Logic:** The geodetic transformation is only half of a defensible survey deliverable. The other half is independent proof that the transformation produced accurate, usable output. The QA engine compares the software's reprojected output against an independent survey CSV of Ground Control Points (GCPs) and Checkpoints (CPs), thereby reporting positional accuracy using RMSE methodology consistent with ASPRS Positional Accuracy Standards, Edition 2.

### Why GCPs and CPs Must Be Separated

GCPs are the control points used by the photogrammetry software during processing to align the model to real-world coordinates. CPs are deliberately held back during processing, specifically so they can independently verify the model's accuracy afterward.

**Crucial Decision:** If the QA engine validated accuracy using GCPs (or a mix of GCPs and CPs), the result would be circular. GCPs are mathematically forced to fit well during processing, since they were used to *create* the model. This would produce an artificially optimistic accuracy figure rather than a genuine independent assessment.

```
DEFINE filter_checkpoints(survey_csv, type_column, checkpoint_value):

    STEP 1: Present every column in the CSV to the user, and require them to
            map: Point ID, Easting, Northing, Elevation, Point Type.

    STEP 2: Show the unique values found in the Point Type column.
            REQUIRE the user to specify which exact value represents a
            Checkpoint (e.g. "CP"), rather than assuming a fixed string.

    STEP 3: Filter the CSV to rows matching that exact value.
            IF no rows match: HALT with a clear error.
            (We do not silently fall back to validating against all points,
            since that would reintroduce the circular validation problem.)

    STEP 4: Proceed to accuracy assessment using ONLY this filtered set.
```

### Vertical Accuracy (Z): KD-Tree Inverse Distance Weighting

**Logic:** For DEM (DSM/DTM) outputs, the true elevation at a checkpoint's exact coordinate can be read directly from the raster via bilinear sampling. For LAS point clouds, there is no continuous surface to sample, only discrete points scattered irregularly in space. The nearest single point is not necessarily representative, so we instead query the 5 nearest neighbours and weight them by inverse distance.

```
DEFINE sample_las_elevation(point_cloud, checkpoint_coordinate, search_radius):

    STEP 1: Build a KD-Tree spatial index of all X,Y coordinates in the
            point cloud (enables fast nearest-neighbour lookup over
            millions of points).

    STEP 2: FOR EACH checkpoint:
        QUERY the 5 nearest point cloud points within the search radius.
        IF none found within radius: SKIP this checkpoint.

        CALCULATE weights = 1 / distance for each of the 5 points
        (closer points influence the result more than farther ones).

        ESTIMATE elevation = weighted average of the 5 points' Z values.

    STEP 3: Compare estimated elevation against the checkpoint's surveyed
            True_Z to calculate Delta_Z, Mean Bias, and RMSE.
```

**Crucial Decision — Search Radius and Index Safety:** A search radius of 0.5m was used after testing showed some genuinely correct checkpoints failing to match any point within the tighter radius, particularly on point clouds with lower spatial density at survey edges. The lookup also keys results by the DataFrame's own index (`{i: np.nan for i in df.index}`) rather than a sequential list position. This guards against silent misalignment if the checkpoint subset has been filtered or re-indexed earlier in the pipeline, ensuring each computed elevation is always matched back to the correct original row rather than relying on row order being preserved by coincidence.

### Horizontal Accuracy (X, Y): Automated Target Detection

**Logic:** For orthomosaics, the true coordinate of each checkpoint can be compared against where that physical target *actually appears* in the processed image. This requires automatically locating the target within a small search window around the checkpoint's surveyed coordinate.

**Crucial Decision — Dynamic Search Window Sizing:** The search window must be sized to the user's actual physical target, not a fixed arbitrary value. A window significantly larger than the target risks including unrelated high-contrast features (gravel, vegetation, shadows) in the detection calculation, pulling the result away from the true target location. The user is asked for their target's physical size, and the search radius is derived from it directly:

```
search_radius = (physical_target_size / 2) + placement_tolerance_margin
```

**Crucial Decision — Corner Detection via Centroid, Not Single Maximum:** For checkerboard targets, Harris corner detection responds strongly to every internal corner of the board, not just its centre. Taking the single strongest corner response risks landing on any one corner of the board. This introduces a positional bias on the order of the board's own physical size.

```
DEFINE locate_checkerboard_target(image_window):

    STEP 1: Run Harris corner detection across the cropped search window.

    STEP 2: Threshold the result, keeping every pixel scoring above 10% of
            the maximum corner response in this window (not just the single
            strongest pixel).

    STEP 3: CALCULATE the centroid (mean X, mean Y) of all pixels that
            passed the threshold.

    This centroid converges toward the board's true geometric centre,
    since the board's corners are arranged symmetrically around it —
    whereas any single corner is not.
```

For painted or marker-style targets (dots, crosses, solid shapes), Otsu thresholding isolates the target from the background by contrast, and the centroid of its largest contour is used directly via image moments — appropriate since these targets typically have no internal corner structure for Harris detection to exploit.

### Per-Point Diagnostic Logging

**Logic:** An aggregate "Detected Targets: 2/3" result tells the user *that* a point failed, but not *why*. Without a specific reason, diagnosing a failed checkpoint means manually re-deriving the search window, re-checking the orthomosaic bounds, and re-inspecting the image by hand — exactly the slow, manual process this software exists to avoid.

**Crucial Decision:** Each failure mode in the detection pipeline is checked and reported individually, rather than allowing a single generic `except: continue` to silently absorb every possible cause:

```
DEFINE diagnose_detection_failure(checkpoint, search_window):

    IF checkpoint coordinate falls outside the orthomosaic's bounds:
        REPORT "Coordinates are completely outside the Orthomosaic bounds."

    ELSE IF the search window cannot be read (e.g. on the extreme edge of
            the map, where a full window cannot be extracted):
        REPORT "Could not read image window (Target is on the extreme edge
                of the map)."

    ELSE IF the search window contains no image data at all (NoData):
        REPORT "Search window is empty/black (Target falls in NoData area)."
        (This specifically catches checkpoints sitting in low-overlap
        regions near flight-corridor edges, where Harris detection would
        otherwise run against pure noise and silently return a
        meaningless result rather than failing visibly.)

    ELSE IF no corners/contours are found above threshold within the
            search radius:
        REPORT "Found 0 checkerboard corners within {radius}m." (or
               equivalent for marker targets)
```

This converts an opaque statistical shortfall into an actionable, point-by-point diagnostic trail — directly informed by real-world testing where checkpoints near the edge of a flight corridor's overlap zone produced detection failures that an aggregate RMSE figure alone would not explain.

### QA-Only Mode

**Logic:** The reprojection step (OSTN15/OSGM15 transformation) and the QA step (target detection, RMSE calculation) are logically independent once an output file exists. Forcing a full re-reprojection every time the report is needed, wastes processing time on large rasters or point clouds for no benefit, since the geodetic output does not change between QA attempts.

```
DEFINE qa_only_routing(args):

    IF --qa-only flag is set:
        SKIP the reprojection step entirely.
        ASSUME args.output already points to a previously-generated,
        correctly transformed file.
        PROCEED directly to QA Column Mapping and accuracy assessment.
    ELSE:
        RUN reprojection as normal, THEN proceed to QA if requested.
```

This supports an iterative QA workflow: a user can re-run accuracy assessment repeatedly against the same already-transformed output while adjusting target size or reviewing diagnostic output, without re-paying the cost of the geodetic transformation each time.

### Statistical Reporting

RMSE is calculated based on the ASPRS Positional Accuracy Standards, Edition 2, which favours direct RMSE reporting over the legacy 95% confidence multiplier approach (the older multiplier methodology assumes normally distributed, symmetric error in X and Y, which does not always hold for UAV survey data). The PDF report states the survey's total control point count, GCP count, and CP count transparently. Sample size context is left for the reader to interpret alongside the RMSE figures themselves.

#### The Mathematics Behind the RMSE Figures

ASPRS Edition 2 defines positional accuracy in terms of Root Mean Square Error (RMSE) computed independently per axis, then combined for radial (2D) and spherical (3D) reporting. For `n` independent checkpoints, where each checkpoint has a known surveyed coordinate (the "true" value) and a value read from the software's reprojected output (the "model" value):

**Per-axis error (residual) for a single checkpoint i:**

```
ΔX_i = X_model_i - X_true_i
ΔY_i = Y_model_i - Y_true_i
ΔZ_i = Z_model_i - Z_true_i
```

**Per-axis RMSE, across all n checkpoints:**

```
RMSE_X = sqrt( (1/n) * Σ(ΔX_i²) )
RMSE_Y = sqrt( (1/n) * Σ(ΔY_i²) )
RMSE_Z = sqrt( (1/n) * Σ(ΔZ_i²) )
```

This is implemented directly as a single vectorised NumPy operation rather than a manual summation loop:

```
DEFINE calculate_rmse(deltas):
    RETURN sqrt( mean( deltas² ) )
```

For the horizontal engine, `deltas` is the array of `Img_E - True_E` (or `Img_N - True_N`) values across every successfully detected checkpoint. For the vertical engine, `deltas` is the array of `Model_Z - True_Z` values. Squaring before averaging means a single large outlier is penalised more heavily than several small errors of the same total magnitude. This is a deliberate property of RMSE consistent with how ASPRS defines the metric.

**Radial RMSE (combining X and Y into a single 2D horizontal figure):**

```
RMSE_R = sqrt( RMSE_X² + RMSE_Y² )
```

This is the Pythagorean combination of the two independent axis errors — it answers "how far off, in a straight line on the ground, is the average checkpoint" rather than reporting X and Y error separately.

**Spherical RMSE (combining horizontal and vertical into a single 3D figure, used in the combined report):**

```
RMSE_3D = sqrt( RMSE_R² + RMSE_Z² )
```

Equivalently, `sqrt( RMSE_X² + RMSE_Y² + RMSE_Z² )`, since `RMSE_R²` already equals `RMSE_X² + RMSE_Y²`. This is only computed when both a vertical assessment (DEM/LAS against the CSV) and a horizontal assessment (orthomosaic reference) have been run on the same checkpoint set, and is exactly the figure produced in the combined `"3d"` report type.

**Mean Bias (Z only):**

```
Mean_Bias_Z = (1/n) * Σ(ΔZ_i)
```

Unlike RMSE, this is signed rather than squared. It answers a different question: not "how large are the errors on average" (RMSE) but "is there a systematic upward or downward trend across the survey" (bias). A small RMSE alongside a non-trivial mean bias would suggest a consistent offset (e.g. a calibration issue) rather than random scatter; this is reported separately precisely so the two effects aren't aggregated into a single number.

**Why this aligns with ASPRS Edition 2 specifically, rather than the older Edition 1 / NSSDA approach:**  Edition 1 and the historical National Standard for Spatial Data Accuracy (NSSDA) report a 95% confidence interval derived by multiplying RMSE by a fixed constant (1.96 for a single axis, 1.7308 for circular/radial error), under the assumption that errors are normally distributed and symmetric between X and Y. Edition 2 instead reccommends reporting RMSE directly, since UAV survey error is not reliably symmetric.