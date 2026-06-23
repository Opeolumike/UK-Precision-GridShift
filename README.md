# UK Precision GridShift
A CLI and GUI geospatial processing software for reprojecting RGB Orthomosaics, Multispectral Orthomosaics, DSMs, DTMs, and LAS Point Clouds from WGS84 UTM Zone 30N to British National Grid / Ordnance Datum Newlyn using Ordnance Survey OSTN15 and OSGM15 transformation grids.

[Watch Demo Here](https://michaelopeoluwa.com/portfolio/uk-precision-gridshift-ostn15-osgm15-transformation/)

### Features
* High-Precision Geodetic Transformation: Applies OSTN15 horizontal and OSGM15 vertical grid transformations.
* Broad Data Compatibility: Processes UAV photogrammetry and LiDAR-derived datasets, including RGB/Multispectral Orthomosaics (.tif), DSMs/DTMs (.tif), and LAS Point Clouds (.las).
* Hybrid Deployment: Features a traditional CLI for reproducible scripting, alongside an interactive GUI mode for simple, standalone Windows desktop use.
* Automated QA Reporting: Evaluates positional accuracy using independent checkpoints, and reports results following the [American Society for Photogrammetry and Remote Sensing (ASPRS) Edition 2 (v2.0) RMSE methodology](https://publicdocuments.asprs.org/PositionalAccuracyStd-Ed2-V2).
* Automated Report Generation: Produces structured PDF reports for horizontal and vertical accuracy assessment.
* Flexible Environments: Runs locally via a standalone .exe or Conda environment, and supports cloud processing via Google Colab (CLI mode only)

### Use Case Example

Construction companies increasingly use UAV photogrammetry and LiDAR-derived datasets to create detailed 3D representations of sites. However, these datasets are not always correctly aligned with national coordinate reference systems without an appropriate geodetic transformation.

Small positional errors in digital terrain models and mapping products can affect downstream engineering workflows, including earthworks calculations, design decisions, and site measurements. Standard mathematical transformations (Helmert) can return metre-level differences in the UK.

UK Precision GridShift is designed for UAV and LiDAR-derived geospatial datasets used in construction, civil engineering, and survey workflows. It enables transformation into the British National Grid with associated vertical datum correction (ODN), supporting applications such as terrain analysis, volumetrics, GIS integration, and engineering data preparation.

> ⚠️ **Please note:** This software is designed specifically for England, Scotland, and Wales. It is not suitable for Northern Ireland, which uses a different datum and geoid model.

### Setup Instructions

Depending on your environment, please follow the specific setup instructions below before running the software.

#### Option A: Local Machine (Conda Recommended)

> **⚠️ Hardware Note:** Applying OSTN15/OSGM15 shifts to high-resolution orthomosaics, DSMs, and Point Clouds is memory-intensive. Ensure your machine has at least 16GB of available RAM. For systems with lower specifications, **Option B: Google Colab** is recommended.

**1. Create a Conda environment if you do not have one yet**

```bash
conda create -n gridshift python=3.12
```

**2. Activate the environment**
```bash
conda activate gridshift
```

**3. Install Dependencies**

Ensure you have the required packages installed in your Conda environment. It is also recommended to install these using Conda to prevent conflicts with other packages:
```bash
conda install -c conda-forge pyproj laspy numpy rasterio opencv fpdf2 pandas scipy
```
**4. Data Placement**

Ensure the Transformation_Grids folder and your input files are placed in the same directory as `gridshift_cli.py`. For the point cloud specifically, keep the folder containing the .las files in the same directory.


#### Option B: Google Colab

**1. Mount your Google Drive**

Create a new Colab notebook and run the standard drive mounting cell:

```bash
from google.colab import drive
drive.mount('/content/drive')
```

**2. Install Dependencies and Change Directory** 

```
%pip install pyproj rasterio laspy opencv-python-headless fpdf2 pandas scipy -q
%cd /content/drive/MyDrive/Folder_Name/  
```
Change "Folder_Name" to the exact Google Drive folder you kept `gridshift_cli.py` , your input files and the Transformation_Grids folder.

**3. Data Placement**

Ensure the Transformation_Grids folder and your input files are placed in the same directory (the Drive folder) as `gridshift_cli.py`. For the point cloud specifically, keep the folder containing the `.las` files in the same directory.

### Running the software

The software supports two modes: a scriptable **CLI mode** for batch processing, and an interactive **GUI mode** for double-click use with no command-line knowledge required.

#### GUI Mode (No Arguments)

**Running from source (requires Python and the setup above):**

```bash
python gridshift_cli.py
```

This opens an interactive console session with numbered menus and native file/folder picker dialogs for selecting your input file, output location, grids folder, and optional GCPs/Checkpoints CSV.

**Using the pre-built `.exe` (no Python or setup required):**

Download **[UK_Precision_Gridshift_EXE.zip file Here](https://github.com/Opeolumike/UK-Precision-GridShift/releases/download/v1.1.0/UK_Precision_Gridshift_EXE.zip)**. **Unzip it first** — running the `.exe` from inside the zip archive directly (without extracting) will fail, since it needs to read the `Transformation_Grids` folder sitting alongside it on disk.

After unzipping, you'll have:

```
UK_Precision_Gridshift_EXE/
├── UK_Precision_GridShift.exe
└── Transformation_Grids/
    ├── ostn15_etrs_to_osgb.gsb
    └── uk_os_osgm15_gb.tif
```

Place your input files — your orthomosaic/DSM/DTM `.tif`, your LAS folder, and your Ground Control Points CSV — into this same `UK_Precision_Gridshift_EXE` folder, alongside the `.exe` and `Transformation_Grids`. Then double-click `UK_Precision_GridShift.exe` and follow the prompts. The file picker dialogs will default to this folder, making your input files easy to find.

#### CLI Mode (With Arguments)

Whether you are in a local terminal or using Colab, the execution commands are identical. Colab users simply add `!` before python, i.e `!python`.

**RGB Orthomosaic**
```
python gridshift_cli.py --type ortho --input "RGB_Ortho.tif" --output "RGB_Ortho_BNG.tif" --grids "Transformation_Grids"
```

**Multispectral Orthomosaic**
```
python gridshift_cli.py --type multi --input "Multispectral_Ortho.tif" --output "Multispectral_Ortho_BNG.tif" --grids "Transformation_Grids"
```

**Digital Surface Model (DSM) and Digital Terrain Model (DTM)**
```
python gridshift_cli.py --type dem --input "DSM_DTM.tif" --output "DSM_DTM_BNG_ODN.tif" --grids "Transformation_Grids"
```

**Point Clouds (LAS Directory)**
```
python gridshift_cli.py --type las --input "Point_Cloud_Folder" --output "Point_Cloud_BNG" --grids "Transformation_Grids"
```
> **Note:** You can change `input ""` and `output ""` to whatever your input file/folder is named and your preferred output file/folder name.

### Optional: Accuracy QA Reporting

If you have an independent survey CSV containing your Ground Control Points (GCPs) and Checkpoints (CPs), the software can automatically verify the positional accuracy of its output and generate a PDF report.

Add the `--qa-file` flag (CLI mode), or select your CSV when prompted (GUI mode). Replace `"Survey_Control.csv"` below with whatever your own GCP/CP CSV file is actually named:

```
python gridshift_cli.py --type ortho --input "RGB_Ortho.tif" --output "RGB_Ortho_BNG.tif" --grids "Transformation_Grids" --qa-file "Survey_Control.csv"
```

For Multispectral, DEM (DSM/DTM), and LAS outputs, also pass `--ortho-reference` with a corresponding RGB orthomosaic, since these data types alone carry no visual contrast for automated target detection:

```
python gridshift_cli.py --type multi --input "Multispectral_Ortho.tif" --output "Multispectral_Ortho_BNG.tif" --grids "Transformation_Grids" --qa-file "Survey_Control.csv" --ortho-reference "RGB_Ortho_BNG.tif"
```

```
python gridshift_cli.py --type dem --input "DSM.tif" --output "DSM_BNG_ODN.tif" --grids "Transformation_Grids" --qa-file "Survey_Control.csv" --ortho-reference "RGB_Ortho_BNG.tif"
```

> ⚠️ **Important:** `--ortho-reference` must point to your RGB orthomosaic **after** it has already been reprojected to BNG by this software (i.e. the output of a previous `--type ortho` run), not the original WGS84 UTM Zone 30N orthomosaic straight from your photogrammetry software. This applies whether your orthomosaic came from a standalone photogrammetry drone or from the RGB camera bundled with an integrated LiDAR sensor payload. The QA engine compares checkpoint coordinates (in BNG) against pixel locations in the orthomosaic, so the orthomosaic must already be in BNG for that comparison to be meaningful. If you haven't reprojected your RGB orthomosaic yet, do that first (RGB Orthomosaic type, in either CLI or GUI mode), then use that output as your reference.

You'll be guided through:
1. **Column mapping** — telling the software which columns in your CSV correspond to Point ID, Easting, Northing, Elevation, and Point Type.
2. **Checkpoint identification** — selecting the exact value (e.g. `CP`) that marks a row as an independent checkpoint, so accuracy is assessed only against points that did not influence the model.
3. **Target type and size** — for horizontal QA, specifying whether you used checkerboard or painted/marker targets, and their physical size, so the software can automatically locate them in the orthomosaic.

The software will then generate a PDF report (`<filename>_QA_Report_<TYPE>.pdf`) summarising RMSE values, following ASPRS Positional Accuracy Standards Edition 2 RMSE-based evaluation methodology.

For DEMs and LAS point clouds, `--ortho-reference` similarly allows verifying horizontal accuracy alongside the native vertical assessment.

#### Re-running QA Without Re-Transforming

If you're tuning QA parameters (target size, target type) and want to test against an already-reprojected output without repeating the geodetic transformation, add `--qa-only`:

```
python gridshift_cli.py --type dem --input "DSM.tif" --output "DSM_BNG_ODN.tif" --grids "Transformation_Grids" --qa-file "Survey_Control.csv" --qa-only
```

This skips reprojection entirely and assumes `--output` already points to a previously-generated, correctly transformed file, going straight to QA. Useful for quickly iterating on detection settings without re-paying the processing cost each time, especially on large rasters or point clouds.

## How to Access the Grid Files Directly from the Source 
The grid files used in this software were retrieved from the official sources listed below. If you choose to download them independently instead of using the pre-configured `Transformation_Grids` files, you have two ways to ensure the software runs correctly:

*   **OSTN15 (Horizontal):** [Download Here](https://www.ordnancesurvey.co.uk/documents/resources/OSTN15-NTv2.zip) 
*   **OSGM15 (Vertical):** [Download Here](https://cdn.proj.org/uk_os_OSGM15_GB.tif)


**Note on Integration:** The software is configured to look for lowercase filenames (`ostn15_etrs_to_osgb.gsb` and `uk_os_osgm15_gb.tif`). If you download the files directly, note that the OSTN15 zip contains several files. The specific one you need is **`OSTN15_NTv2_ETRStoOSGB.gsb`**.

**To make the software work, you can either:**
1.  **Rename the files:** Rename `OSTN15_NTv2_ETRStoOSGB.gsb` to `ostn15_etrs_to_osgb.gsb` and `uk_os_OSGM15_GB.tif` to `uk_os_osgm15_gb.tif`.

2.  **Edit `gridshift_cli.py`:** Keep the original filenames and simply update the filename in `gridshift_cli.py` to match the raw filenames exactly.

---

## Accuracy Considerations and Intended Use

It is important to note that:

- OSTN15 provides centimetre-level horizontal transformation accuracy across Great Britain.
- OSGM15 provides geoid separation modelling for deriving orthometric heights from ellipsoidal heights.
- Actual end-user accuracy depends on:
  - UAV GNSS quality
  - Ground Control Points (GCPs) quality
  - Image alignment quality
  - Sensor calibration
  - Photogrammetric processing quality

Therefore, the software's outputs should be interpreted within the broader survey accuracy standards and photogrammetric processing quality.