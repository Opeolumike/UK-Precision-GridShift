#!/usr/bin/env python3
"""Build the standalone UK Precision GridShift executable with PyInstaller.

Run from the repository folder, inside the GridShift conda environment with
PyInstaller installed:

    python build_exe.py

It produces dist/UK_Precision_Gridshift_EXE/ holding UK_Precision_GridShift.exe
and the Transformation_Grids folder, plus dist/UK_Precision_Gridshift_EXE.zip
for the release. The build and dist folders are ignored by Git.

The executable bundles PROJ's coordinate database and GDAL's data files, which
gridshift_cli.py points PROJ and GDAL to at start-up when it runs frozen. PROJ's
transformation grids are left out on purpose: GridShift applies OSTN15 and
OSGM15 only from the Transformation_Grids folder beside the executable.
"""
import os
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__
import pyproj

# Repository folder (where this script and gridshift_cli.py live)
REPO = Path(__file__).resolve().parent

# Names used for the executable and the release folder
EXE_NAME = "UK_Precision_GridShift"
RELEASE_NAME = "UK_Precision_Gridshift_EXE"

# Working folders, all inside build/ and dist/ so Git ignores them
BUILD = REPO / "build"
DIST = REPO / "dist"
STAGE = BUILD / "bundle_data"

# File types of PROJ transformation grids, which are not bundled
GRID_SUFFIXES = {".tif", ".tiff", ".gsb", ".gtx", ".byn", ".lla", ".ct2", ".gvb", ".asc", ".jpg"}


def find_gdal_data():
    """Return GDAL's data folder for this environment."""
    # Ask rasterio first, as it knows where its own GDAL looks
    try:
        from rasterio._env import GDALDataFinder
        found = GDALDataFinder().search()
        if found:
            return Path(found)
    except ImportError:
        pass

    # Otherwise try the usual conda locations (Windows, then Linux and macOS)
    for candidate in (Path(sys.prefix) / "Library" / "share" / "gdal", Path(sys.prefix) / "share" / "gdal"):
        if (candidate / "gdalvrt.xsd").exists() or (candidate / "header.dxf").exists():
            return candidate
    raise SystemExit("Could not find GDAL's data folder in this environment.")


def stage_proj_data():
    """Copy PROJ's database and small support files, leaving out grids."""
    source = Path(pyproj.datadir.get_data_dir())
    target = STAGE / "proj"
    target.mkdir(parents=True, exist_ok=True)

    # proj.db is required, so stop early if it is missing
    if not (source / "proj.db").exists():
        raise SystemExit(f"proj.db not found in {source}.")

    # Copy every file except transformation grids
    copied = 0
    for item in source.iterdir():
        if item.is_file() and item.suffix.lower() not in GRID_SUFFIXES:
            shutil.copy2(item, target / item.name)
            copied += 1
    print(f"PROJ data: {copied} files from {source} (grids left out)")
    return target


def build():
    """Run PyInstaller, then assemble the release folder and zip."""
    # Start from clean working folders so no old files slip into the build
    shutil.rmtree(BUILD, ignore_errors=True)
    shutil.rmtree(DIST, ignore_errors=True)

    # Data folders the frozen script expects: 'proj' and 'gdal_data'
    proj_data = stage_proj_data()
    gdal_data = find_gdal_data()
    print(f"GDAL data: {gdal_data}")

    # One-file console executable from gridshift_cli.py
    PyInstaller.__main__.run([
        str(REPO / "gridshift_cli.py"),
        "--name", EXE_NAME,
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        "--distpath", str(BUILD / "exe"),
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
        "--add-data", f"{proj_data}{os.pathsep}proj",
        "--add-data", f"{gdal_data}{os.pathsep}gdal_data",
        # rasterio loads several of its modules only at run time
        "--collect-submodules", "rasterio",
        # fpdf2 carries font metric files it reads at run time
        "--collect-data", "fpdf",
        # GridShift never uses pkg_resources, and its start-up hook can fail
        # when frozen, so leave it out
        "--exclude-module", "pkg_resources",
    ])

    # Release folder: the executable beside the Transformation_Grids folder
    release = DIST / RELEASE_NAME
    release.mkdir(parents=True)
    exe_file = next((BUILD / "exe").glob(EXE_NAME + "*"))
    shutil.copy2(exe_file, release / exe_file.name)
    shutil.copytree(REPO / "Transformation_Grids", release / "Transformation_Grids")

    # Zip of the release folder for the GitHub release
    archive = shutil.make_archive(str(DIST / RELEASE_NAME), "zip", root_dir=DIST, base_dir=RELEASE_NAME)
    size_mb = exe_file.stat().st_size / 1e6
    print(f"\nBuilt {release / exe_file.name} ({size_mb:.0f} MB)")
    print(f"Release zip: {archive}")


if __name__ == "__main__":
    build()
