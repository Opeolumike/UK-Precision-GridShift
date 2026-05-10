#!/usr/bin/env python3
# ==============================================================================
# UK Precision GridShift CLI
# Reprojecting RGB Orthomosaics, Multispectral Orthomosaics, DSMs, and LAS Point Clouds through the CLI
# Transformation: OSTN15 (Horizontal) and OSGM15 (Vertical)
# From: EPSG:32630 (UTM 30N)
# To: EPSG:27700 (BNG) + ODN Height
# April 2026
# ==============================================================================

import os
import glob
import argparse
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import pyproj
from pyproj import Transformer, CRS
import laspy

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
def reproject_dsm_odn(input_path, output_path, grid_folder):
    print("Initialising DSM BNG/ODN Reprojection...")
    
    # PyProj Setup (For the Z-Shift)
    pyproj.datadir.append_data_dir(grid_folder)
    
    # Define the absolute paths to both grid files
    ostn15_path = os.path.abspath(os.path.join(grid_folder, "ostn15_etrs_to_osgb.gsb"))
    osgm15_path = os.path.abspath(os.path.join(grid_folder, "uk_os_osgm15_gb.tif"))
    
    ## Throw an error if the horizontal grid is not found
    # Create an empty list to collect any missing file errors
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

    # If the list is not empty, throw all collected errors simultaneously!
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
    # Create an empty list to collect any missing file errors
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

    # If the list is not empty, throw all collected errors simultaneously!
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
# COMMAND LINE INTERFACE (CLI) ROUTING
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="UK Precision GridShift - High-precision UAV data transformation to BNG/ODN.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "-t", "--type", 
        required=True, 
        choices=['multi', 'ortho', 'dsm', 'las'], 
        help="The type of data being processed:\n"
             "  multi : Multispectral Orthomosaic (.tif)\n"
             "  ortho : RGB Orthomosaic (.tif)\n"
             "  dsm   : Digital Surface Model (.tif)\n"
             "  las   : Point Cloud Directory"
    )
    
    parser.add_argument(
        "-i", "--input", 
        required=True, 
        help="Path to the input file (for Rasters) or input directory (for LAS)."
    )
    
    parser.add_argument(
        "-o", "--output", 
        required=True, 
        help="Path to the output file (for Rasters) or output directory (for LAS)."
    )
    
    parser.add_argument(
        "-g", "--grids", 
        required=True, 
        help="Path to the directory containing the OSTN15/OSGM15 grid files."
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print(" UK Precision GridShift")
    print("="*60)

    # Route the arguments to the correct function
    try:
        if args.type == 'multi':
            reproject_multi_bng(args.input, args.output, args.grids)
        elif args.type == 'ortho':
            reproject_ortho_rgb(args.input, args.output, args.grids)
        elif args.type == 'dsm':
            reproject_dsm_odn(args.input, args.output, args.grids)
        elif args.type == 'las':
            reproject_point_cloud_bng_odn(args.input, args.output, args.grids)
    except Exception as e:
        print(f"\n❌ TERMINATED: {e}")