# Architecture and Geodetic Logic Document for UK Precision GridShift

**Prepared By:** Michael Opeoluwa

**Date:** May 2026

**Purpose:** To explain the architecture, mathematical pipelines, and design logic for the UK Precision GridShift. This document serves as the reference for the geodetic transformations applied within the tool, specifically defending the pipeline architecture against common PROJ library misconceptions.

---

## Part 1: System Initialisation and Failsafes

**Logic:** Before any pixels or points are moved, the tool must verify the environment. Geodetic transformations fail silently if grid files are missing, falling back to lower-accuracy transformation methods. This tool enforces strict validation up front.

```
START CLI ROUTING
    ACCEPT Arguments: Type of Data, Input Path, Output Path, Grid Folder Path

    MATCH Data Type:
        IF 'multi' -> Route to Multispectral Function
        IF 'ortho' -> Route to RGB Function
        IF 'dsm'   -> Route to DSM Function
        IF 'las'   -> Route to Point Cloud Function

    CATCH Errors:
        If any step fails, terminate and print the exact error to the user.
END
```

---

## Part 2: 2D Planimetric Shifts (RGB & Multispectral)

**Logic:** For 2D raster datasets, only horizontal coordinate transformations are required. We use rasterio's internal warping engine tied strictly to the OSTN15 grid.

**Crucial Decision:** For multispectral and raw RGB data, Nearest Neighbour resampling is required to preserve original spectral reflectance values. Using bilinear or cubic interpolation would mathematically average the adjacent pixels, altering the original spectral reflectance values captured by the drone sensors.

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

## Part 3: The Raster Elevation Transformation (DSM) & Geodetic Defense

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
DEFINE reproject_dsm_odn(input, output, grids):

    STEP 1: Validate both OSTN15 (Horizontal) and OSGM15 (Vertical) grid files.
            IF either is missing, aggregate the errors and HALT.

    STEP 2: Define the Z-Shift PROJ Pipeline
        PIPELINE =
            1. REVERSE BNG Eastings/Northings back to OSGB36 Lat/Lon  (+inv +proj=tmerc)
            2. REVERSE OSGB36 back to WGS84 Lat/Lon                   (+inv +proj=hgridshift)
            3. APPLY OSGM15 Geoid Undulation to get ODN Height         (+inv +proj=vgridshift)

    STEP 3: Planimetric Warp (The X/Y Shift)
        OPEN input DSM
        WARP to BNG using OSTN15 (Rasterio handles the precise footprint)
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

---

## Part 5: Accuracy Considerations and Intended Use

It is important to note that:

- OSTN15 provides centimetre-level horizontal transformation accuracy across Great Britain.
- OSGM15 provides geoid separation modelling for deriving orthometric heights from ellipsoidal heights.
- Actual end-user accuracy depends on:
  - UAV GNSS quality
  - Ground Control Points (GCPs) quality
  - Image alignment quality
  - Sensor calibration
  - Photogrammetric processing quality

Therefore, the tool's outputs should be interpreted within the broader survey accuracy standards and photogrammetric processing quality.
