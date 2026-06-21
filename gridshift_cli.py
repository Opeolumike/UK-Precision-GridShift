#!/usr/bin/env python3
# ==============================================================================
# UK Precision GridShift CLI
# Reprojecting RGB Orthomosaics, Multispectral Orthomosaics (photogrammetry), 
# DSMs, DTMs, and LAS Point Clouds (photogrammetry and LiDAR) through the CLI
# Transformation: OSTN15 (Horizontal) and OSGM15 (Vertical)
# From: EPSG:32630 (UTM 30N)
# To: EPSG:27700 (BNG) + ODN Height
# Accuracy Verification: Reports accuracy metrics following ASPRS Edition 2 RMSE concepts
# ==============================================================================

import os
import sys

# ==============================================================================
# PyInstaller Spatial Library Runtime Hook
# This MUST happen before importing rasterio or pyproj
# ==============================================================================
if getattr(sys, 'frozen', False):
    # We are running as a compiled .exe
    bundle_dir = sys._MEIPASS

    # Point PROJ and GDAL to the hidden temp folders created by the .spec file
    os.environ["PROJ_DATA"] = os.path.join(bundle_dir, 'proj')
    os.environ["PROJ_LIB"] = os.path.join(bundle_dir, 'proj')
    os.environ["GDAL_DATA"] = os.path.join(bundle_dir, 'gdal_data')

import glob
import argparse
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import pyproj
from pyproj import Transformer, CRS
import laspy
import cv2
import pandas as pd
from scipy.spatial import cKDTree
from fpdf import FPDF
import datetime
from zoneinfo import ZoneInfo
from rasterio.windows import Window
import tkinter as tk
from tkinter import filedialog

import warnings

# This silences DeprecationWarnings so users only see clean output
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ==============================================================================
# 1. MULTISPECTRAL ORTHOMOSAIC
# ==============================================================================
## Define the function
def reproject_multi_bng(input_path, output_path, grid_folder):
    print("Initialising Multispectral Orthomosaic BNG Reprojection...")
     
    # Tell PyProj where to find custom grids
    pyproj.datadir.append_data_dir(grid_folder)
    
    # Define the absolute path to the horizontal grid file
    ostn15_path = os.path.abspath(os.path.join(grid_folder, "ostn15_etrs_to_osgb.gsb"))
    
    # Throw an error if the grid file is not found
    if not os.path.exists(ostn15_path):
        raise FileNotFoundError(
            f"❌ CRITICAL ERROR: Transformation grid not found at {ostn15_path}. "
            "Ensure the file is named correctly. Strict BNG precision is enforced."
        )
    
    # Define the high-precision BNG pipeline
    bng_base = "+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy +units=m +no_defs"
    bng_2d_pipeline = f"{bng_base} +nadgrids={ostn15_path}"

    with rasterio.open(input_path) as src:
        transform, width, height = calculate_default_transform("EPSG:32630", "EPSG:27700", src.width, src.height, *src.bounds)
        # Grab the nodata value from the source file (or default to 0)
        src_nodata = src.nodata or 0
        
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': 'EPSG:27700',
            'transform': transform,
            'width': width,
            'height': height,
            'nodata': src_nodata 
        })

        with rasterio.open(output_path, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                print(f"Processing Band {i} of {src.count}...")
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs="EPSG:32630",
                    dst_transform=transform,
                    dst_crs=bng_2d_pipeline,
                    src_nodata=src_nodata,
                    dst_nodata=src_nodata, 
                    resampling=Resampling.nearest
                )
    print(f"✅ Success: {output_path}")

# ==============================================================================
# 2. RGB ORTHOMOSAIC
# ==============================================================================
## Define the function
def reproject_ortho_rgb(input_path, output_path, grid_folder):
    print("Initialising RGB Orthomosaic BNG Reprojection...")
    
    # Tell PyProj where the grids are safely stored
    pyproj.datadir.append_data_dir(grid_folder)
  
    # Define the absolute path to the horizontal grid file
    ostn15_path = os.path.abspath(os.path.join(grid_folder, "ostn15_etrs_to_osgb.gsb"))
    
    # Throw an error if the grid file is not found
    if not os.path.exists(ostn15_path):
        raise FileNotFoundError(
            f"❌ CRITICAL ERROR: Transformation grid not found at {ostn15_path}. "
            "Ensure the file is named correctly. Strict BNG precision is enforced."
        )
    
    # Define the high-precision BNG pipeline
    bng_base = "+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy +units=m +no_defs"
    bng_2d_pipeline = f"{bng_base} +nadgrids={ostn15_path}"

    with rasterio.open(input_path) as src:
        src_nodata = src.nodata
        nodata = src_nodata if src_nodata is not None else 0

        transform, width, height = calculate_default_transform("EPSG:32630", "EPSG:27700", src.width, src.height, *src.bounds)

        kwargs = src.meta.copy()
        kwargs.update({
            'crs': 'EPSG:27700',
            'transform': transform,
            'width': width,
            'height': height,
            'nodata': nodata
        })

        with rasterio.open(output_path, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                print(f"Processing Band {i} of {src.count}...")
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs="EPSG:32630",
                    dst_transform=transform,
                    dst_crs=bng_2d_pipeline,
                    src_nodata=src_nodata,
                    dst_nodata=nodata,
                    resampling=Resampling.nearest
                )
    print(f"✅ Success: {output_path}")

# ==============================================================================
# 3. DIGITAL SURFACE MODEL (WITH OSGM15 VERTICAL SHIFT)
# ==============================================================================
## Define the function
def reproject_dem_odn(input_path, output_path, grid_folder):
    print("Initialising BNG/ODN Reprojection...")
    
    # PyProj Setup (For the Z-Shift)
    pyproj.datadir.append_data_dir(grid_folder)
    
    # Define the absolute paths to both grid files
    ostn15_path = os.path.abspath(os.path.join(grid_folder, "ostn15_etrs_to_osgb.gsb"))
    osgm15_path = os.path.abspath(os.path.join(grid_folder, "uk_os_osgm15_gb.tif"))
    
    ## Throw an error if the horizontal grid is not found
    missing_errors = []

    # Check the horizontal grid and add to list if missing
    if not os.path.exists(ostn15_path):
        missing_errors.append(
            f"❌ HORIZONTAL GRID MISSING: Not found at {ostn15_path}.\n"
            "   Ensure the file is named correctly. Strict BNG precision is enforced."
        )

    # Check the vertical grid and add to list if missing
    if not os.path.exists(osgm15_path):
        missing_errors.append(
            f"❌ VERTICAL GRID MISSING: Not found at {osgm15_path}.\n"
            "   Ensure the file is named correctly. Accurate ODN heights cannot be calculated."
        )

    if missing_errors:
        combined_errors = "\n\n".join(missing_errors)
        raise FileNotFoundError(f"\n\n{combined_errors}")
        
    # Define the high-precision BNG pipeline
    bng_base = "+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy +units=m +no_defs"
    bng_2d_pipeline = f"{bng_base} +nadgrids={ostn15_path}"
    
    # Build the Z-shift pipeline using PyProj
    z_shift_pipeline = (
        f"+proj=pipeline "
        f"+step +inv +proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy "
        f"+step +inv +proj=hgridshift +grids={ostn15_path} "
        f"+step +inv +proj=vgridshift +grids={osgm15_path} +multiplier=1"
    )
    bng_z_shifter = Transformer.from_pipeline(z_shift_pipeline)
    
    print("Executing rasterio planimetric shift...")
    with rasterio.open(input_path) as src:
        transform, width, height = calculate_default_transform("EPSG:32630", "EPSG:27700", src.width, src.height, *src.bounds)

        kwargs = src.meta.copy()
        kwargs.update({
            'crs': 'EPSG:27700',
            'transform': transform,
            'width': width,
            'height': height,
            'nodata': -9999,
            'dtype': 'float32'
        })

        with rasterio.open(output_path, 'w', **kwargs) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs="EPSG:32630",
                dst_transform=transform,
                dst_crs=bng_2d_pipeline,
                src_nodata=src.nodata,
                dst_nodata=-9999,
                resampling=Resampling.bilinear
            )

        print("Applying OSGM15 vertical shift...")
         # Apply vertical correction tile-by-tile
        with rasterio.open(output_path, 'r+') as dst:
            for ji, window in dst.block_windows(1):
                dest = dst.read(1, window=window)
                mask = dest != -9999

                if np.any(mask):
                    win_transform = rasterio.windows.transform(window, transform)
                    rows, cols = np.indices(dest.shape)
                    xs = win_transform.c + cols * win_transform.a + rows * win_transform.b
                    ys = win_transform.f + cols * win_transform.d + rows * win_transform.e

                    _, _, z_odn = bng_z_shifter.transform(xs[mask], ys[mask], dest[mask])

                    dest[mask] = z_odn
                    dst.write(dest, 1, window=window)

            dst.update_tags(VERTICAL_DATUM="ODN", GEOID_MODEL="OSGM15")
    print(f"✅ Success: {output_path}")

# ==============================================================================
# 4. POINT CLOUDS (LAS)
# ==============================================================================
## Define the function
def reproject_point_cloud_bng_odn(input_folder, output_folder, grid_folder):
    print("Initialising Point Cloud BNG/ODN Reprojection...")
    # Tell PyProj where to find custom grids
    pyproj.datadir.append_data_dir(grid_folder)

    # Define the absolute paths to both grid files
    ostn15_path = os.path.abspath(os.path.join(grid_folder, "ostn15_etrs_to_osgb.gsb"))
    osgm15_path = os.path.abspath(os.path.join(grid_folder, "uk_os_osgm15_gb.tif"))

    ## Throw an error if the horizontal grid is not found
    missing_errors = []

    # Check the horizontal grid and add to list if missing
    if not os.path.exists(ostn15_path):
        missing_errors.append(
            f"❌ HORIZONTAL GRID MISSING: Not found at {ostn15_path}.\n"
            "   Ensure the file is named correctly. Strict BNG precision is enforced."
        )

    # Check the vertical grid and add to list if missing
    if not os.path.exists(osgm15_path):
        missing_errors.append(
            f"❌ VERTICAL GRID MISSING: Not found at {osgm15_path}.\n"
            "   Ensure the file is named correctly. Accurate ODN heights cannot be calculated."
        )

    if missing_errors:
        combined_errors = "\n\n".join(missing_errors)
        raise FileNotFoundError(f"\n\n{combined_errors}")
        
    # Set the Pipeline: Forward horizontal shift, Inverse vertical shift
    z_shift_pipeline = (
        "+proj=pipeline "
        "+step +inv +proj=utm +zone=30 +ellps=WGS84 "
        f"+step +inv +proj=vgridshift +grids={osgm15_path} +multiplier=1 "
        f"+step +proj=hgridshift +grids={ostn15_path} "
        "+step +proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 "
        "+x_0=400000 +y_0=-100000 +ellps=airy +units=m +no_defs"
    )
    transformer = Transformer.from_pipeline(z_shift_pipeline)

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    las_files = sorted(glob.glob(os.path.join(input_folder, "*.las")))
    total_files = len(las_files)
    print(f"Found {total_files} .las files. Starting transformation...")

    for index, las_path in enumerate(las_files, 1):
        fname = os.path.basename(las_path)
        try:
            las = laspy.read(las_path)
            if len(las.points) > 0:
                # Transform the coordinates
                x_out, y_out, z_out = transformer.transform(np.array(las.x), np.array(las.y), np.array(las.z))
                valid_mask = np.isfinite(x_out) & np.isfinite(y_out) & np.isfinite(z_out)
                
                # Create the new LAS object
                if np.any(valid_mask):
                    new_las = laspy.create(point_format=las.header.point_format, file_version=las.header.version)
                    try:
                        # Attempt to add CRS for laspy v2.0+
                        new_las.header.add_crs(CRS.from_epsg(27700))
                    except Exception:
                        pass
                    
                    # Scale and Offset
                    new_las.header.offsets = [np.floor(np.min(x_out[valid_mask])),
                                              np.floor(np.min(y_out[valid_mask])),
                                              np.floor(np.min(z_out[valid_mask]))]
                    new_las.header.scales = [0.001, 0.001, 0.001]

                    # Assign the transformed coordinates
                    new_las.x = x_out[valid_mask]
                    new_las.y = y_out[valid_mask]
                    new_las.z = z_out[valid_mask]

                    # Transfer extra attributes (Colors, Intensity, etc.)
                    for dim in las.point_format.dimension_names:
                        if dim not in ['X', 'Y', 'Z', 'x', 'y', 'z']:
                            new_las[dim] = las[dim][valid_mask]

                    # Save the file
                    out_name = fname.replace(".las", "_BNG_ODN.las")
                    new_las.write(os.path.join(output_folder, out_name))

            if index % 50 == 0 or index == total_files:
                print(f"Progress: {index}/{total_files} tiles completed...")

        except Exception as e:
            print(f"❌ Error in {fname}: {e}")

    print(f"\n--- SUCCESS: Point Cloud Reprojection Complete ---")

# ==============================================================================
# 5. QUALITY ASSURANCE (QA) ENGINE
# ==============================================================================

# Interactive Column Mapper
def interactive_column_mapping(df):
    """Present an interactive menu to map CSV columns to expected GridShift fields."""
    print("\n------------------------------------------------------------")
    print(" 🛠  INTERACTIVE COLUMN MAPPING")
    print("    Note: Please select the column that defines Point Type.")
    print("------------------------------------------------------------")
    cols = list(df.columns)
    for i, col in enumerate(cols):
        print(f"  [{i}] {col}")
    
    def get_selection(prompt, required=True):
        while True:
            val = input(f"\nSelect column for {prompt} (Enter index number): ").strip()
            if not required and val == "": return None
            if val.isdigit() and int(val) < len(cols): return cols[int(val)]
            print("❌ Invalid selection. Please enter a valid index number.")

    mapping = {
        'id': get_selection("Point ID/Name"),
        'easting': get_selection("Easting"),
        'northing': get_selection("Northing"),
        'elevation': get_selection("Elevation"),
        'type_col': get_selection("Point Type/Classification", required=True),
        'lat_rms': get_selection("Lateral RMS (Optional, press Enter to skip)", required=False),
        'elev_rms': get_selection("Elevation RMS (Optional, press Enter to skip)", required=False)
    }

    # Now let the user pick which exact value from the type_col is the CP
    type_col = mapping['type_col']
    unique_types = df[type_col].unique()
    print(f"\nValues found in '{type_col}': {unique_types}")
    while True:
        val = input(f"Enter the exact value that represents your Checkpoints: ").strip()
        if val in [str(u) for u in unique_types]:
            mapping['checkpoint_val'] = val
            break
        print("❌ That value does not exist in the column. Please try again.")

    return mapping

# PDF report generator for accuracy auditing
class QAReport(FPDF):
    def header(self):
        # Corporate Banner
        self.set_fill_color(24, 43, 73)  
        self.rect(0, 0, 210, 32, 'F')
        self.set_y(10)
        self.set_text_color(255, 255, 255)
        self.set_font("helvetica", "B", 18)
        self.cell(5)
        self.cell(0, 8, "UK Precision GridShift", border=False, ln=True, align="L")
        self.set_font("helvetica", "", 11)
        self.cell(5)
        self.cell(0, 6, "Automated Positional Accuracy Report", border=False, ln=True, align="L")
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_text_color(128, 128, 128)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Engineered by UK Precision GridShift v1.0  |  Page {self.page_no()}", 0, 0, "C")

    def section_title(self, title):
        self.set_font("helvetica", "B", 12)
        self.set_fill_color(235, 238, 242)  
        self.set_text_color(24, 43, 73)
        self.cell(0, 9, f"  {title}", 0, 1, 'L', fill=True)
        self.ln(3)

    def meta_row(self, label, value, status=None):
        self.set_font("helvetica", "B", 10)
        self.set_text_color(70, 70, 70)
        self.cell(65, 6, label, 0, 0)
        self.set_font("helvetica", "", 10)
        
        if status == "PASS":
            self.set_text_color(0, 128, 0)
            self.set_font("helvetica", "B", 10)
        elif status == "REVIEW":
            self.set_text_color(200, 100, 0)
            self.set_font("helvetica", "B", 10)
        else:
            self.set_text_color(0, 0, 0)
            
        self.cell(0, 6, str(value), 0, 1)

# Logic to generate standardised PDF report (Updated for ASPRS Edition 2 Compliant Reporting)
def generate_pdf_report(qa_df, stats, report_type, args, total_pts, cp_count, gcp_count, detected_count):
    pdf = QAReport()
    pdf.add_page()
    
    # Process Summary Block
    pdf.section_title("Project & Processing Summary")
    pdf.meta_row("Date Generated:", datetime.datetime.now(ZoneInfo("Europe/London")).strftime('%Y-%m-%d %H:%M:%S %Z'))
    pdf.meta_row("Source Model:", os.path.basename(args.input))
    pdf.meta_row("Data Type:", args.display_name)
    pdf.meta_row("Source Coordinate System:", "EPSG:32630 (UTM Zone30N)")
    pdf.meta_row("New Coordinate System:", "EPSG:27700 (OSGB36)")
    
    # ASPRS Standard Compliance Reference
    pdf.meta_row("Accuracy Standard:", "ASPRS Positional Accuracy Standards, Edition 2 (v2.0) - RMSE-based evaluation")
    pdf.meta_row("Standard Reference:", "https://publicdocuments.asprs.org/PositionalAccuracyStd-Ed2-V2")
    
    if report_type in ["vertical", "3d"]:
        pdf.meta_row("Vertical Datum:", "Ordnance Datum Newlyn (ODN)")
        pdf.meta_row("Geodetic Engine:", "Strict OSTN15 / OSGM15 Transformation")
    else:
        pdf.meta_row("Vertical Datum:", "N/A (2D Horizontal Product)")
        pdf.meta_row("Geodetic Engine:", "Strict OSTN15 Transformation")
    pdf.ln(4)

    # Survey Control Summary
    pdf.section_title("Survey Control Summary")
    pdf.meta_row("Total Control Points:", total_pts)
    pdf.meta_row("Ground Control Points (GCP):", gcp_count)
    pdf.meta_row("Independent Checkpoints (CP):", cp_count)
    pdf.meta_row("Accuracy Assessment Basis:", "Independent Checkpoints (CP) only")
    pdf.ln(4)
    
    # Statistical Table
    pdf.section_title(f"Statistical Overview ({report_type.upper()} Analysis)")
    pdf.meta_row("Checkpoints Successfully Detected:", detected_count)
    
    if report_type == "3d":
        pdf.meta_row("RMSE (X):", f"{stats['rmse_x']:.3f} m")
        pdf.meta_row("RMSE (Y):", f"{stats['rmse_y']:.3f} m")
        pdf.meta_row("RMSE (Z):", f"{stats['rmse_z']:.3f} m")
        pdf.meta_row("Radial RMSE (R):", f"{stats['rmse_r']:.3f} m")
        pdf.meta_row("Spherical RMSE (3D):", f"{stats['rmse_3d']:.3f} m")
    elif report_type == "vertical":
        pdf.meta_row("Mean Bias (Z):", f"{stats['mean']:.3f} m")
        pdf.meta_row("RMSE (Z):", f"{stats['rmse']:.3f} m")
    elif report_type == "horizontal":
        pdf.meta_row("RMSE (X):", f"{stats['rmse_x']:.3f} m")
        pdf.meta_row("RMSE (Y):", f"{stats['rmse_y']:.3f} m")
        pdf.meta_row("Radial RMSE (R):", f"{stats['rmse_r']:.3f} m")
    pdf.ln(4)
    
    # Residuals Table
    pdf.section_title("Point Residuals Data")
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(0, 0, 0)
    
    if report_type == "3d":
        pdf.cell(30, 8, "Point ID", 1, 0, 'C', fill=True)
        pdf.cell(40, 8, "Delta X (m)", 1, 0, 'C', fill=True)
        pdf.cell(40, 8, "Delta Y (m)", 1, 0, 'C', fill=True)
        pdf.cell(40, 8, "Delta Z (m)", 1, 0, 'C', fill=True)
        pdf.cell(40, 8, "3D Vector (m)", 1, 1, 'C', fill=True)
        
        pdf.set_font("helvetica", "", 9)
        for _, row in qa_df.iterrows():
            dE = row['Img_E'] - row['True_E']
            dN = row['Img_N'] - row['True_N']
            dZ = row['Delta_Z']
            vector_3d = np.sqrt(dE**2 + dN**2 + dZ**2)
            
            pdf.set_text_color(200, 0, 0) if vector_3d > 0.1 else pdf.set_text_color(0, 0, 0)
            pdf.cell(30, 8, str(row[args.col_id]), 1, 0, 'C')
            pdf.cell(40, 8, f"{dE:.3f}", 1, 0, 'C')
            pdf.cell(40, 8, f"{dN:.3f}", 1, 0, 'C')
            pdf.cell(40, 8, f"{dZ:.3f}", 1, 0, 'C')
            pdf.cell(40, 8, f"{vector_3d:.3f}", 1, 1, 'C')

    elif report_type == "vertical":
        pdf.cell(30, 8, "Point ID", 1, 0, 'C', fill=True)
        pdf.cell(25, 8, "Type", 1, 0, 'C', fill=True)
        pdf.cell(35, 8, "True Z (m)", 1, 0, 'C', fill=True)
        pdf.cell(35, 8, "Model Z (m)", 1, 0, 'C', fill=True)
        pdf.cell(35, 8, "Delta Z (m)", 1, 1, 'C', fill=True)
        
        pdf.set_font("helvetica", "", 9)
        for _, row in qa_df.iterrows():
            pdf.set_text_color(200, 0, 0) if abs(row['Delta_Z']) > 0.05 else pdf.set_text_color(0, 0, 0)
            pdf.cell(30, 8, str(row[args.col_id]), 1, 0, 'C')
            pdf.cell(25, 8, str(row[args.col_type]), 1, 0, 'C')
            pdf.cell(35, 8, f"{row['True_Z']:.3f}", 1, 0, 'C')
            pdf.cell(35, 8, f"{row['Model_Z']:.3f}", 1, 0, 'C')
            pdf.cell(35, 8, f"{row['Delta_Z']:.3f}", 1, 1, 'C')

    elif report_type == "horizontal":
        pdf.cell(30, 8, "Point ID", 1, 0, 'C', fill=True)
        pdf.cell(35, 8, "Shift Vector (m)", 1, 0, 'C', fill=True)
        pdf.cell(45, 8, "Model E / N", 1, 0, 'C', fill=True)
        pdf.cell(45, 8, "True E / N", 1, 1, 'C', fill=True)
        
        pdf.set_font("helvetica", "", 9)
        for _, row in qa_df.iterrows():
            pdf.set_text_color(200, 0, 0) if row['Shift_m'] > 0.05 else pdf.set_text_color(0, 0, 0)
            pdf.cell(30, 8, str(row[args.col_id]), 1, 0, 'C')
            pdf.cell(35, 8, f"{row['Shift_m']:.3f}", 1, 0, 'C')
            pdf.cell(45, 8, f"{row['Img_E']:.2f} / {row['Img_N']:.2f}", 1, 0, 'C')
            pdf.cell(45, 8, f"{row['True_E']:.2f} / {row['True_N']:.2f}", 1, 1, 'C')
            
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    out_name = f"{base_name}_QA_Report_{report_type.upper()}.pdf"
    pdf.output(out_name)
    print(f"[SUCCESS] Report generated: {out_name}")

# Logic to sample elevation from Point Clouds using KD-Tree for spatial accuracy
def sample_las_elevation(las_dir, df, args, search_radius=0.5): # Increased radius to 0.5m
    las_elevations = {i: np.nan for i in df.index} 
    las_files = glob.glob(os.path.join(las_dir, "*.las")) if os.path.isdir(las_dir) else [las_dir]
    
    print(f"    -> Indexing Point Cloud(s) for QA (Checking {len(las_files)} files...)")
    for las_file in las_files:
        try:
            las = laspy.read(las_file)
            if len(las.points) == 0: continue # Skip empty files safely
            
            tree = cKDTree(np.vstack((las.x, las.y)).transpose())
            for i, row in df.iterrows():
                if not pd.isna(las_elevations[i]): continue
                dist, idx = tree.query([row[args.col_e], row[args.col_n]], k=5, distance_upper_bound=search_radius)
                valid = dist < float('inf')
                if np.any(valid):
                    weights = 1.0 / np.maximum(dist[valid], 1e-6)
                    las_elevations[i] = np.sum(weights * las.z[idx[valid]]) / np.sum(weights)
        except Exception: 
            pass # Silently skip unreadable LAS files

    # Return as a flat list in the exact order of the dataframe
    return [las_elevations[i] for i in df.index]


# Engine for Vertical QA (Z-Accuracy)
def run_universal_qa_vertical(processed_path, file_type, df, args):
    print("\n[QA] Initialising Vertical Accuracy Assessment (Z)...")
    
    # Filter for CPs with exact match
    cps = df[df[args.col_type] == args.checkpoint_val].copy()
    if cps.empty:
        print("❌ ERROR: No rows found matching your Checkpoint value.")
        return None

    if file_type == 'dem':
        elevations = []
        with rasterio.open(processed_path) as src:
            for index, row in cps.iterrows():
                try:
                    val = next(src.sample([(row[args.col_e], row[args.col_n])]))[0]
                    elevations.append(np.nan if val == src.nodata else val)
                except Exception: elevations.append(np.nan)
        cps['Model_Z'] = elevations
    elif file_type == 'las':
        cps['Model_Z'] = sample_las_elevation(processed_path, cps, args)

    cps = cps.dropna(subset=['Model_Z'])
    
    # Catch silent failures and warn the user
    if cps.empty: 
        print("⚠️ WARNING: No valid Z-elevations could be extracted from the model at the checkpoint locations.")
        print("   (This usually means the checkpoints fall outside the point cloud boundaries, or the 0.5m search radius is too small.)")
        return None
        
    cps['True_Z'] = cps[args.col_z]
    cps['Delta_Z'] = cps['Model_Z'] - cps['True_Z']

    stats = {
        'rmse': np.sqrt((cps['Delta_Z'] ** 2).mean()),
        'mean': cps['Delta_Z'].mean()
    }
    
    print("\n========================================")
    print(f" 📊 GRIDSHIFT VERTICAL: {file_type.upper()}")
    print("========================================")
    print(f" Checkpoints Analysed : {len(cps)}")
    print(f" Mean Bias (Z)        : {stats['mean']:.3f} m")
    print(f" RMSE (Z)             : {stats['rmse']:.3f} m")
    print("========================================")
    return cps, stats, "vertical"

# Engine for Horizontal QA (X,Y Accuracy)
def run_automated_horizontal_qa(ortho_path, df, args):
    print("\n[QA] Initialising OpenCV Horizontal Accuracy Assessment (X,Y)...")
    
    # Filter for CPs via exact match
    cps = df[df[args.col_type] == args.checkpoint_val].copy()
    if cps.empty:
        print("❌ ERROR: No rows found matching your Checkpoint value.")
        return None
    
    cps['Img_E'], cps['Img_N'], cps['Shift_m'] = np.nan, np.nan, np.nan
    cps['True_E'], cps['True_N'] = cps[args.col_e], cps[args.col_n]

    effective_radius = (args.target_size / 2.0) + 0.5

    with rasterio.open(ortho_path) as src:
        pixel_size_x, pixel_size_y = src.res
        search_pixels = int(effective_radius / pixel_size_x)

        for index, row in cps.iterrows():
            rtk_e, rtk_n = row[args.col_e], row[args.col_n]
            point_id = row[args.col_id]
            
            try: 
                py, px = src.index(rtk_e, rtk_n)
            except Exception: 
                print(f"  [Point {point_id}] ⚠️ Failed: CSV Coordinates ({rtk_e:.1f}, {rtk_n:.1f}) are completely outside the Orthomosaic bounds.")
                continue

            window = Window(col_off=px - (search_pixels//2), row_off=py - (search_pixels//2), width=search_pixels, height=search_pixels)
            try:
                img_data = src.read((1, 2, 3), window=window)
                if img_data.dtype == 'uint16': img_data = (img_data / 256).astype('uint8')
                
                # Check if the search window is mostly black/empty (NoData)
                if not np.any(img_data):
                    print(f"  [Point {point_id}] ⚠️ Failed: Search window is empty/black (Target falls in NoData area).")
                    continue
                    
                gray = cv2.cvtColor(np.transpose(img_data, (1, 2, 0)), cv2.COLOR_RGB2GRAY)
            except Exception: 
                print(f"  [Point {point_id}] ⚠️ Failed: Could not read image window (Target is on the extreme edge of the map).")
                continue

            if args.target_type == 'checkerboard':
                gray = np.float32(gray)
                corners = cv2.cornerHarris(gray, 2, 3, 0.04)

                corner_thresh = corners > 0.1 * corners.max()

                y_coords, x_coords = np.where(corner_thresh)

                if len(x_coords) > 0:
                    target_px = int(np.mean(x_coords))
                    target_py = int(np.mean(y_coords))
                else:
                    print(f"  [Point {point_id}] ⚠️ Failed: Image was read, but OpenCV found 0 checkerboard corners within {effective_radius}m.")
                    continue
                    
            elif args.target_type == 'marker':
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    M = cv2.moments(largest_contour)
                    if M["m00"] != 0:
                        target_px = int(M["m10"] / M["m00"])
                        target_py = int(M["m01"] / M["m00"])
                    else:
                        print(f"  [Point {point_id}] ⚠️ Failed: Marker contour detected, but center mass could not be calculated.")
                        continue
                else:
                    print(f"  [Point {point_id}] ⚠️ Failed: No distinct shapes/markers found within {effective_radius}m.")
                    continue

            # Translate local pixel to global BNG pixel
            global_px = (px - (search_pixels // 2)) + target_px
            global_py = (py - (search_pixels // 2)) + target_py
            img_e, img_n = src.xy(global_py, global_px)
            
            cps.at[index, 'Img_E'], cps.at[index, 'Img_N'] = img_e, img_n
            cps.at[index, 'Shift_m'] = np.hypot(img_e - rtk_e, img_n - rtk_n)

    res = cps.dropna(subset=['Shift_m'])
    if res.empty: 
        print("\n❌ CRITICAL: Vision Engine failed to detect any targets based on the diagnostics above.")
        return None

    # Calculate statistics (Pure RMSE per modern ASPRS standards)
    stats = {
        'rmse_x': np.sqrt(((res['Img_E'] - res['True_E']) ** 2).mean()),
        'rmse_y': np.sqrt(((res['Img_N'] - res['True_N']) ** 2).mean())
    }
    stats['rmse_r'] = np.sqrt(stats['rmse_x']**2 + stats['rmse_y']**2)

    print("\n========================================")
    print(" 🎯 HORIZONTAL (X,Y)")
    print("========================================")
    print(f" Detected Targets          : {len(res)} / {len(cps)}")
    print(f" RMSE (X)                  : {stats['rmse_x']:.3f} m")
    print(f" RMSE (Y)                  : {stats['rmse_y']:.3f} m")
    print(f" Radial RMSE (R)           : {stats['rmse_r']:.3f} m")
    print("========================================")
    
    return res, stats, "horizontal"

# ==============================================================================
# GUI FILE PICKER HELPERS
# ==============================================================================
def open_file_dialog(title, filetypes, initialdir):
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    path = filedialog.askopenfilename(title=title, filetypes=filetypes, initialdir=initialdir)
    root.destroy()
    return path

def open_dir_dialog(title, initialdir):
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    path = filedialog.askdirectory(title=title, initialdir=initialdir)
    root.destroy()
    return path

def save_file_dialog(title, default_ext, initialdir, initialfile):
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    path = filedialog.asksaveasfilename(title=title, defaultextension=default_ext, initialdir=initialdir, initialfile=initialfile)
    root.destroy()
    return path

# ==============================================================================
# COMMAND LINE INTERFACE (CLI) ROUTING
# ==============================================================================
if __name__ == "__main__":
    
    print("\n" + "="*60)
    print(" UK Precision GridShift")
    print("="*60)

    # Determine the directory where the .exe or script is running
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # ---------------------------------------------------------
    # The "Double-Click" Interactive GUI Mode
    # ---------------------------------------------------------
    if len(sys.argv) == 1:
        print("\nInteractive Mode Activated.")
        print("Please use the popup windows to select your files.\n")
        
        args = argparse.Namespace()
        
        print("1. Select Data Type:")
        print("   [1] Multispectral Orthomosaic")
        print("   [2] RGB Orthomosaic")
        print("   [3] Digital Elevation Model (DSM/DTM)")
        print("   [4] LAS Point Cloud")
        while True:
            type_choice = input("Enter choice (1-4): ").strip()
            if type_choice in ['1', '2', '3', '4']:
                break
            print("❌ Invalid choice.")
            
        type_map = {'1': 'multi', '2': 'ortho', '3': 'dem', '4': 'las'}
        args.type = type_map.get(type_choice)
        
        # Determine appropriate file types for the dialog
        if args.type == 'las':
            # Input Folder
            print("\nWaiting for Input Folder selection (containing .las files)...")
            args.input = open_dir_dialog("Select Input Folder containing LAS files", base_dir)
            if not args.input:
                print("❌ Operation cancelled.")
                input("Press Enter to exit...")
                sys.exit(0)
            print(f"Selected Input Folder: {args.input}")
            
            # Output Folder Strategy
            default_out_folder = f"{args.input}_BNG_ODN"
            print(f"\n[Output Setup] Suggested Output Folder: {default_out_folder}")
            print("Press [ENTER] to accept this default, or type 'c' to manually choose a different folder.")
            out_choice = input("Choice: ").strip().lower()
            
            if out_choice == 'c':
                print("\nWaiting for Output Folder selection...")
                args.output = open_dir_dialog("Select Output Folder for Reprojected LAS", os.path.dirname(args.input))
                if not args.output:
                    print("❌ Operation cancelled.")
                    input("Press Enter to exit...")
                    sys.exit(0)
            else:
                args.output = default_out_folder
                
            print(f"Selected Output Folder: {args.output}")

        else:
            file_types = [("TIFF Files", "*.tif;*.tiff")]
            out_ext = ".tif"
            
            # Input File
            print("\nWaiting for Input File selection...")
            args.input = open_file_dialog("Select Input File", file_types, base_dir)
            if not args.input:
                print("❌ Operation cancelled.")
                input("Press Enter to exit...")
                sys.exit(0)
            print(f"Selected Input: {args.input}")
                
            # Output File
            print("\nWaiting for Output File selection...")
            default_out_name = os.path.basename(args.input).replace(out_ext, f"_BNG_ODN{out_ext}")
            args.output = save_file_dialog("Save Output File As", out_ext, os.path.dirname(args.input), default_out_name)
            if not args.output:
                print("❌ Operation cancelled.")
                input("Press Enter to exit...")
                sys.exit(0)
            print(f"Selected Output: {args.output}")

        # Grids Folder
        print("\nWaiting for Grids Folder selection...")
        args.grids = open_dir_dialog("Select folder containing OSTN15/OSGM15 Grids", base_dir)
        if not args.grids:
            print("❌ Operation cancelled.")
            input("Press Enter to exit...")
            sys.exit(0)
        print(f"Selected Grids: {args.grids}")

        # Dynamic Initial Directory for QA Pickers
        qa_initial_dir = args.input if args.type == 'las' else os.path.dirname(args.input)

        # QA CSV
        print("\nWaiting for QA CSV selection (Optional)...")
        args.qa_file = open_file_dialog("Select QA Checkpoints CSV (Cancel to skip)", [("CSV Files", "*.csv")], qa_initial_dir)
        args.qa_only = False
        if args.qa_file:
            print(f"Selected QA File: {args.qa_file}")
            skip_reproj = input("\n⏭️ Do you want to SKIP reprojection and ONLY run QA on an existing file? (y/n): ").strip().lower()
            if skip_reproj == 'y':
                args.qa_only = True
        else:
            print("QA Skipped.")
            
        # Reference Ortho (if applicable)
        args.ortho_reference = None
        if args.qa_file and args.type in ['dem', 'las', 'multi']:
            print("\nWaiting for Reference Orthomosaic selection (Optional)...")
            args.ortho_reference = open_file_dialog("Select Reference RGB Ortho for Horizontal QA (Cancel to skip)", [("TIFF Files", "*.tif;*.tiff")], qa_initial_dir)
            if args.ortho_reference:
                print(f"Selected Reference Ortho: {args.ortho_reference}")
            else:
                print("Horizontal QA Skipped.")
                
        args.target_type = None

    # ---------------------------------------------------------
    # The Standard Command-Line Mode
    # ---------------------------------------------------------
    else:
        parser = argparse.ArgumentParser(
            description="UK Precision GridShift - High-precision UAV data transformation to BNG/ODN.",
            formatter_class=argparse.RawTextHelpFormatter
        )

        parser.add_argument("-t", "--type", required=True, choices=['multi', 'ortho', 'dem', 'las'], help="Data type: multi, ortho, dem, las")
        parser.add_argument("-i", "--input", required=True, help="Input file or directory")
        parser.add_argument("-o", "--output", required=True, help="Output file or directory")
        parser.add_argument("-g", "--grids", required=True, help="Directory containing OSTN15/OSGM15 grid files")
        
        qa_group = parser.add_argument_group('Optional QA Reporting')
        qa_group.add_argument('--qa-file', type=str, default=None, help="Path to original Surveyor RTK CSV")
        qa_group.add_argument('--qa-only', action='store_true', help="Skip reprojection and only run QA on an existing output file.")
        qa_group.add_argument('--target-type', type=str, choices=['checkerboard', 'marker'], default=None, help="Type of physical GCP marker. 'checkerboard' or 'marker' (Painted/Dots). If omitted, the tool asks interactively.")
        qa_group.add_argument('--ortho-reference', type=str, default=None, help="Path to accompanying 2D Orthomosaic. Required for Horizontal QA on DEMs, LAS, or Multispectral.")

        args = parser.parse_args()

    args.display_name = args.type.upper()
    if args.type == 'multi':
        args.display_name = 'Multispectral Orthomosaic'
    elif args.type == 'ortho':
        args.display_name = 'RGB Orthomosaic'
    elif args.type == 'las':
        args.display_name = 'LAS Point Cloud'
    elif args.type == 'dem':
        print("\n⛰️  [DEM Setup] Please classify this elevation model:")
        print("  [1] Digital Surface Model (DSM)")
        print("  [2] Digital Terrain Model (DTM)")
        while True:
            choice = input("Enter 1 or 2: ").strip()
            if choice == '1':
                args.display_name = 'Digital Surface Model'
                break
            elif choice == '2':
                args.display_name = 'Digital Terrain Model'
                break
            else:
                print("❌ Invalid choice. Please enter 1 or 2.")
    
    # Interactive QA Prompt
    qa_path = args.qa_file
    while True:
        if qa_path and os.path.exists(qa_path):
            break
        elif not qa_path:
            break
        else:
            print("\n⚠️ No GCP/Checkpoints CSV found for verification.")
            print("Do you want to skip the optional accuracy verification?")
            print("  [1] Skip verification (Proceed to Reprojection without QA)")
            print("  [2] Cancel (Exit Tool)")
            print("  [3] I want to confirm (Enter correct CSV path manually)")
            
            choice = input("Enter 1, 2, or 3: ").strip()
            if choice == '1':
                qa_path = None
                break
            elif choice == '2':
                print("Operation cancelled by user.")
                if len(sys.argv) == 1: input("Press Enter to exit...")
                sys.exit(0)
            elif choice == '3':
                if len(sys.argv) == 1:
                    qa_path = open_file_dialog("Select QA Checkpoints CSV", [("CSV Files", "*.csv")], base_dir)
                else:
                    qa_path = input("Enter the full path to the QA CSV file: ").strip()
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

    # Execute Core Reprojection
    if getattr(args, 'qa_only', False):
        print("\n⏭️  [QA ONLY MODE] Skipping reprojection. Analyzing existing output file...")
    else:
        try:
            if args.type == 'multi': reproject_multi_bng(args.input, args.output, args.grids)
            elif args.type == 'ortho': reproject_ortho_rgb(args.input, args.output, args.grids)
            elif args.type == 'dem': reproject_dem_odn(args.input, args.output, args.grids)
            elif args.type == 'las': reproject_point_cloud_bng_odn(args.input, args.output, args.grids)
        except Exception as e:
            print(f"\n❌ TERMINATED: {e}")
            if len(sys.argv) == 1: input("Press Enter to exit...")
            sys.exit(1)

    # Execute Optional QA
    if qa_path:
        try:
            df = pd.read_csv(qa_path)
            
            # Column Mapping for QA
            mapping = interactive_column_mapping(df)
            args.col_id = mapping['id']
            args.col_e = mapping['easting']
            args.col_n = mapping['northing']
            args.col_z = mapping['elevation']
            args.col_type = mapping['type_col'] 
            args.checkpoint_val = mapping['checkpoint_val'] # The exact value (e.g., 'CP')
            
            total_pts = len(df)
            cp_df = df[df[args.col_type] == args.checkpoint_val]
            cp_count = len(cp_df)
            gcp_count = total_pts - cp_count
            
            qa_results_horizontal = None
            qa_results_vertical = None
            
            needs_horizontal = args.type == 'ortho' or (args.type in ['multi', 'dem', 'las'] and args.ortho_reference and os.path.exists(args.ortho_reference))
            
            if needs_horizontal and not args.target_type:
                print("\n🎯 [QA Setup] What type of physical GCP targets were used on site?")
                print("  [1] Checkerboard (Standard high-contrast corners)")
                print("  [2] Painted/Marker (Dots, crosses, or solid shapes)")
                
                while True:
                    t_choice = input("Enter 1 or 2: ").strip()
                    if t_choice == '1':
                        args.target_type = 'checkerboard'
                        break
                    elif t_choice == '2':
                        args.target_type = 'marker'
                        break
                    else:
                        print("Invalid choice. Please enter 1 or 2.")
            
            if needs_horizontal:
                if args.target_type == 'checkerboard':
                    try:
                        user_size = input("\n📏 Enter physical checkerboard size in metres (e.g., 0.5 for 50cm): ").strip()
                        args.target_size = float(user_size) if user_size else 0.5
                    except ValueError:
                        print("⚠️ Invalid input. Defaulting to 0.5m.")
                        args.target_size = 0.5
                else:
                    args.target_size = 0.5

            # Execute QA Engines
            if args.type == 'ortho':
                qa_results_horizontal = run_automated_horizontal_qa(args.output, df, args)
                
            elif args.type == 'multi':
                if args.ortho_reference and os.path.exists(args.ortho_reference):
                    qa_results_horizontal = run_automated_horizontal_qa(args.ortho_reference, df, args)
                else:
                    print(f"\n[QA Note] Skipping Horizontal Accuracy Assessment. Multispectral sensors lack RGB contrast. Provide an RGB Orthomosaic.")

            elif args.type in ['dem', 'las']:
                qa_results_vertical = run_universal_qa_vertical(args.output, args.type, df, args)
                if args.ortho_reference and os.path.exists(args.ortho_reference):
                    qa_results_horizontal = run_automated_horizontal_qa(args.ortho_reference, df, args)

            # Generate Unified PDF reports
            if qa_results_horizontal and qa_results_vertical:
                res_df_h, stats_h, rep_type_h = qa_results_horizontal
                res_df_v, stats_v, rep_type_v = qa_results_vertical
                
                # Merge dataframes on Point ID
                combined_df = pd.merge(res_df_h, res_df_v, on=args.col_id)
                
                # Combine stats
                combined_stats = {
                    'rmse_x': stats_h['rmse_x'],
                    'rmse_y': stats_h['rmse_y'],
                    'rmse_z': stats_v['rmse'],
                    'rmse_r': stats_h['rmse_r'],
                    'rmse_3d': np.sqrt(stats_h['rmse_r']**2 + stats_v['rmse']**2)
                }
                print("\n========================================")
                print(" 🌐 GENERATING COMBINED 3D REPORT")
                print("========================================")
                generate_pdf_report(combined_df, combined_stats, "3d", args, total_pts, cp_count, gcp_count, len(qa_results_horizontal[0]))
                
            elif qa_results_horizontal:
                res_df_h, stats_h, rep_type_h = qa_results_horizontal
                generate_pdf_report(res_df_h, stats_h, rep_type_h, args, total_pts, cp_count, gcp_count, len(res_df_h))
                
            elif qa_results_vertical:
                res_df_v, stats_v, rep_type_v = qa_results_vertical
                generate_pdf_report(res_df_v, stats_v, rep_type_v, args, total_pts, cp_count, gcp_count, len(res_df_v))

        except Exception as e:
            print(f"\n⚠️ QA Processing Failed: {e}")

    print("\nProcess Complete.")
    if len(sys.argv) == 1:
        input("Press Enter to exit...")