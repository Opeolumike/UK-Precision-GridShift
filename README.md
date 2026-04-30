# UK-Precision-GridShift
A Python-based tool for reprojecting RGB Orthomosaics, Multispectral Orthomosaics, DSMs, and LAS Point Clouds from WGS84 UTM 30N to British National Grid/Ordnance Datum Newlyn using Ordnance Survey OSTN15 and OSGM15 transformation grids.

### Setup Instructions

Depending on your environment, please follow the specific setup instructions below before running the scripts.

#### Option A: Local Jupyter Notebook

If you are running this script locally on your own machine:

**1. Delete Cell 1 and Cell 2**

Cell 1 and Cell 2 are for those who prefer to use Google Colab

**2. Install Dependencies**

Ensure you have the required packages installed in your Conda environment. It is also recommended to install these using Conda to prevent conflicts with other packages:
```bash
conda install -c conda-forge pyproj laspy numpy
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

