# UK-Precision-GridShift
A Python-based tool for reprojecting RGB Orthomosaics, Multispectral Orthomosaics, DSMs, and LAS Point Clouds from WGS84 UTM 30N to British National Grid/Ordnance Datum Newlyn using Ordnance Survey OSTN15 and OSGM15 transformation grids.

### Why Use this Tool?

Standard mathematical transformations (Helmert) can be off by up to 5 metres in the UK. This tool uses the OSGB grid shifts for millimetre-level accuracy.

### Please note 
This tool is designed specifically for England, Scotland, and Wales.

### Setup Instructions

Depending on your environment, please follow the specific setup instructions below before running the scripts.

#### Option A: Local Jupyter Notebook

If you are running this script locally on your own machine:

**1. Delete Cell 1 and Cell 2**

Cell 1 and Cell 2 are for those who prefer to use Google Colab

**2. Install Dependencies**

Ensure you have the required packages installed in your Conda environment. It is also recommended to install these using Conda to prevent conflicts with other packages:
```bash
conda install -c conda-forge pyproj laspy numpy rasterio
```
**3. Data Placement**

Unzip the "Transformation_Grids" file. Ensure the Transformation_Grids folder and your input files are placed directly into the same directory as the scripts. For the point cloud specifically, keep the folder containing the `.las` files in the same directory.


#### Option B: Google Colab

**1. Update the file path in the script to point to the Drive folder** 

Change "Folder_Name" to your exact Google Drive folder name

```bash
BASE_DIR = "/content/drive/MyDrive/Folder_Name/"
```

**2. Data Placement**

Unzip the "Transformation_Grids" file. Ensure the Transformation_Grids folder and your input files are placed directly in the same directory as the scripts (the Drive folder). For the point cloud specifically, keep the folder containing the `.las` files in the same directory.

## How to Access the Grid Files Directly from the Source 

The grid files used in this tool were retrieved from the official sources listed below. If you choose to download them independently instead of using the pre-configured `Transformation_Grids` zip file, you have two ways to ensure the scripts run correctly:

*   **OSTN15 (Horizontal):** [Download Here](https://www.ordnancesurvey.co.uk/documents/resources/OSTN15-NTv2.zip) 
*   **OSGM15 (Vertical):** [Download Here](https://cdn.proj.org/uk_os_OSGM15_GB.tif)


**Note on Integration:** The scripts in this repository are configured to look for lowercase filenames (`ostn15_etrs_to_osgb.gsb` and `uk_os_osgm15_gb.tif`). If you download the files directly, note that the OSTN15 zip contains several files. The specific one you need is **`OSTN15_NTv2_ETRStoOSGB.gsb`**.

**To make the code work, you can either:**
1.  **Rename the files:** Rename `OSTN15_NTv2_ETRStoOSGB.gsb` to `ostn15_etrs_to_osgb.gsb` and `uk_os_OSGM15_GB.tif` to `uk_os_osgm15_gb.tif`.

2.  **Edit the script:** Keep the original filenames and simply update the filename in the scripts to match the raw filenames exactly.
