# UK Precision GridShift
A CLI-based Python tool for reprojecting RGB Orthomosaics, Multispectral Orthomosaics, DSMs, and LAS Point Clouds from WGS84 UTM Zone 30N to British National Grid/Ordnance Datum Newlyn using Ordnance Survey OSTN15 and OSGM15 transformation grids.

### Features
* Reprojects orthomosaics, DSMs, and LAS point clouds from WGS84 UTM Zone 30N to the British National Grid
* Applies OSTN15 horizontal and OSGM15 vertical transformations
* Supports RGB, multispectral, DSM, and LAS datasets
* CLI-based for reproducible batch processing
* Compatible with local Conda environments and Google Colab

### Why Use this Tool?

Standard mathematical transformations (Helmert) can be off by up to 5 metres in the UK. This tool uses the OSTN15/OSGM15 grid shifts to preserve centimetre-level accuracy, provided the input datasets are of survey-grade quality.

> ⚠️ **Please note:** This tool is designed specifically for England, Scotland, and Wales. It is not suitable for Northern Ireland, which uses a different datum and geoid model.

### Setup Instructions

Depending on your environment, please follow the specific setup instructions below before running the tool.

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
conda install -c conda-forge pyproj laspy numpy rasterio
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
%pip install pyproj rasterio laspy -q
%cd /content/drive/MyDrive/Folder_Name/  
```
Change "Folder_Name" to the exact Google Drive folder you kept `gridshift_cli.py` , your input files and the Transformation_Grids folder.

**3. Data Placement**

Ensure the Transformation_Grids folder and your input files are placed in the same directory (the Drive folder) as `gridshift_cli.py`. For the point cloud specifically, keep the folder containing the `.las` files in the same directory.

#### How to Use (CLI Commands)

Whether you are in a local terminal or using Colab, the execution commands are identical — Colab users simply add `!` before python, i.e `!python`.

**RGB Orthomosaic**
```
python gridshift_cli.py --type ortho --input "RGB_Ortho.tif" --output "RGB_Ortho_BNG.tif" --grids "Transformation_Grids"
```

**Multispectral Orthomosaic**
```
python gridshift_cli.py --type multi --input "Multispectral_Ortho.tif" --output "Multispectral_Ortho_BNG.tif" --grids "Transformation_Grids"
```

**Digital Surface Model (DSM)**
```
python gridshift_cli.py --type dsm --input "DSM.tif" --output "DSM_BNG_ODN.tif" --grids "Transformation_Grids"
```

**Point Clouds (LAS Directory)**
```
python gridshift_cli.py --type las --input "Point_Cloud_Folder" --output "Point_Cloud_BNG" --grids "Transformation_Grids"
```
> **Note:** You can change `input ""` and `output ""` to whatever your input file/folder is named and your preferred output file/folder name.

## How to Access the Grid Files Directly from the Source 
The grid files used in this tool were retrieved from the official sources listed below. If you choose to download them independently instead of using the pre-configured `Transformation_Grids` files, you have two ways to ensure the tool runs correctly:

*   **OSTN15 (Horizontal):** [Download Here](https://www.ordnancesurvey.co.uk/documents/resources/OSTN15-NTv2.zip) 
*   **OSGM15 (Vertical):** [Download Here](https://cdn.proj.org/uk_os_OSGM15_GB.tif)


**Note on Integration:** The tool is configured to look for lowercase filenames (`ostn15_etrs_to_osgb.gsb` and `uk_os_osgm15_gb.tif`). If you download the files directly, note that the OSTN15 zip contains several files. The specific one you need is **`OSTN15_NTv2_ETRStoOSGB.gsb`**.

**To make the tool work, you can either:**
1.  **Rename the files:** Rename `OSTN15_NTv2_ETRStoOSGB.gsb` to `ostn15_etrs_to_osgb.gsb` and `uk_os_OSGM15_GB.tif` to `uk_os_osgm15_gb.tif`.

2.  **Edit `gridshift_cli.py`:** Keep the original filenames and simply update the filename in `gridshift_cli.py` to match the raw filenames exactly.
