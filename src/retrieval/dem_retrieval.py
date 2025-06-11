import geopandas as gpd
import rasterio
import rasterio.mask
from rasterio.merge import merge
import requests
import os
import sys
import re

def merge_rasters(raster_paths: list, output_path: str):
    """
    Merges multiple raster files into a single output raster.

    The function handles rasters with different extents and resolutions,
    and ensures the output metadata is correct.

    Args:
        raster_paths (list): A list of string paths to the raster files to be merged.
        output_path (str): The file path where the merged raster will be saved.
    """
    if not raster_paths:
        print("Error: The list of raster paths is empty.")
        return

    print(f"Starting merge for {len(raster_paths)} rasters.")

    try:
        # The merge function from rasterio.merge takes a list of file paths
        # and returns the merged data array and the new transform.
        mosaic, out_trans = merge(raster_paths)

        # We need to copy the metadata from one of the source rasters
        # and update it with the new dimensions and transform.
        with rasterio.open(raster_paths[0]) as src:
            out_meta = src.meta.copy()

        # Update the metadata dictionary with the new dimensions and transform
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_trans,
        })

        # Write the merged mosaic to the output file
        print(f"Writing merged raster to: {output_path}")
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(mosaic)
        
        print("Merge completed successfully.")

    except Exception as e:
        print(f"An error occurred during merging: {e}")

def crop_raster_with_shapefile(raster_file_object, crop_gdf):
    """
    Crops a raster from a file-like object to the extent of a GeoDataFrame.

    Args:
        raster_file_object: A file-like object for a raster dataset (e.g., from open()).
        crop_gdf: A GeoDataFrame containing the polygon(s) to crop with.

    Returns:
        A tuple containing:
        - out_image: The cropped raster data as a numpy array.
        - out_meta: The metadata for the new cropped raster.
    """
    try:
        # Open the raster dataset from the file-like object
        with rasterio.open(raster_file_object) as src:
            # It's crucial to ensure the CRS of the shapefile and raster match.
            # If they don't, reproject the GeoDataFrame to the raster's CRS.
            if src.crs != crop_gdf.crs:
                print(f"CRS mismatch. Reprojecting GeoDataFrame to raster CRS: {src.crs}")
                crop_gdf = crop_gdf.to_crs(src.crs)

            # Get the geometries from the GeoDataFrame for masking
            geometries = crop_gdf.geometry.values

            # Use the mask function to crop the raster
            # - crop=True: ensures the output raster's extent is clipped to the geometry's extent
            # - all_touched=True: includes pixels that are touched by the geometry, not just those with their center inside
            out_image, out_transform = rasterio.mask.mask(
                dataset=src,
                shapes=geometries,
                crop=True,
                all_touched=True
            )

            # Update the metadata for the new, cropped raster
            out_meta = src.meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })

            return out_image, out_meta

    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None

def get_dem(boundary_path, outpath, resolution = '30m', union = True, crop = True):

    # args testing
    if boundary_path == None:
        raise(ValueError, 'Boundary path cannot be None')
    elif not os.path.exists(boundary_path):
        raise(ReferenceError, f'No file at {boundary_path}')

    latlng1 = re.compile(r'.*_n(\d*)w(\d*)_(\d\d\d\d\d\d\d\d).tif')
    latlng2 = re.compile(r'.*_x(\d*)y(\d*)_.*_(\d\d\d\d)_.*.tif')

    # Define the path to your shapefile
    shapefile_path = boundary_path

    # Read the shapefile using geopandas
    boundary = gpd.read_file(shapefile_path)

    # Ensure the GeoDataFrame has a valid geometry
    if boundary.empty or boundary.is_empty.any():
        raise ValueError("The provided shapefile contains no valid geometries.")

    # Calculate the bounding box of the shapefile
    minx, miny, maxx, maxy = boundary.total_bounds

    print(minx, miny, maxx, maxy)

    # Define the API endpoint
    api_url = 'https://tnmaccess.nationalmap.gov/api/v1/products'

    # Define the parameters for the API request

    """
    Options:
    1 arc-second (approximately 30 meters)
    1/3 arc-second (approximately 10 meters)
    1/9 arc-second (approximately 3 meters)"""

    NED_resoluations = {
        '30m': 'National Elevation Dataset (NED) 1 arc-second',
        '10m': 'National Elevation Dataset (NED) 1/3 arc-second',
        '3m': 'National Elevation Dataset (NED) 1/9 arc-second',
        '1m': 'Digital Elevation Model (DEM) 1 meter'
    }

    if resolution not in NED_resoluations.keys():
        raise(ValueError, f'{resolution} not valid. Options include: 30m, 10m, 3m, 1m')

    params = {
        'datasets': NED_resoluations[resolution],
        'bbox': f'{minx},{miny},{maxx},{maxy}',
        'prodFormats': 'GeoTIFF',
        'max': 100
    }

    # Make the API request
    response = requests.get(api_url, params=params)

    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
        items = data.get('items', [])
        
        # Sort for most recent only
        dates = {}
        for i, item in enumerate(items):
            tiff = item['urls']['TIFF']
            ind = i
            print(tiff)
            try:
                lat = int(latlng1.match(tiff).group(1))
                lng = int(latlng1.match(tiff).group(2))
                date = int(latlng1.match(tiff).group(3))
                latlngstr = 'n{}w{}'.format(lat,lng)
                if latlngstr not in dates.keys():
                    dates[latlngstr] = (date,ind)
                else:
                    if date > dates[latlngstr][0]:
                        dates[latlngstr] = (date,ind)
            except:
                lat = int(latlng2.match(tiff).group(1))
                lng = int(latlng2.match(tiff).group(2))
                date = int(latlng2.match(tiff).group(3))
                latlngstr = 'n{}w{}'.format(lat,lng)
                if latlngstr not in dates.keys():
                    dates[latlngstr] = (date,ind)
                else:
                    if date > dates[latlngstr][0]:
                        dates[latlngstr] = (date,ind)
        print('Most recent set, to download:')
        wantitems = []
        for key, val in dates.items():
            wantitems.append(items[val[1]])
            print('\t{}, Date {}'.format(key,val[0]))

        outpaths = []

        # download most recent only
        for item in wantitems:
            download_url = item.get('downloadURL')
            if download_url:
                # Download the file
                file_name = os.path.basename(download_url)
                outfpath = outpath.split('.')[0] + f'_{file_name}'
                outpaths.append(outfpath)
                if os.path.exists(outfpath):
                    print(f'{file_name} exists, SKIPPING...')
                    continue
                print(f'Downloading {file_name}...')
                download_response = requests.get(download_url)
                if download_response.status_code == 200:
                    with open(outfpath, 'wb') as f:
                        f.write(download_response.content)
                    print(f'{file_name} downloaded successfully.')
                else:
                    print(f'Failed to download {file_name}.')
    else:
        print('Failed to retrieve data from the API.')
        print(response.text)

    # crop
    if crop:
        for path in outpaths:
            with open(path, 'rb') as f:
                # Here we call the function with the simulated objects 'f' and 'gdf'
                cropped_image, cropped_meta = crop_raster_with_shapefile(f, boundary)

                # Now, you can save the cropped raster to a new file if needed
                if cropped_image is not None and cropped_meta is not None:
                    output_filename = path
                    with rasterio.open(output_filename, "w", **cropped_meta) as dest:
                        dest.write(cropped_image)
    
    if merge:
        merge_rasters(raster_paths=outpaths, output_path=outpath)
        # clean unwanted rasters
        for path in outpaths:
            os.remove(path)
    
    return output_filename

if __name__ == '__main__':
    # resolutions = ['30m', '10m', '3m']
    resolutions = ['30m']
    for resolution in resolutions:
        get_dem(
            boundary_path=os.path.join('test','retrieval_test.shp'), 
            outpath=os.path.join('test',f'{resolution}_out.tif'),
            resolution=resolution)