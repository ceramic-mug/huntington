import geopandas as gpd
import rasterio
import requests
import os
import sys
import re
import src.retrieval.utility as utility

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
                cropped_image, cropped_meta = utility.crop_raster_with_shapefile(f, boundary)

                # Now, you can save the cropped raster to a new file if needed
                if cropped_image is not None and cropped_meta is not None:
                    output_filename = path
                    with rasterio.open(output_filename, "w", **cropped_meta) as dest:
                        dest.write(cropped_image)
    
    if union:
        utility.merge_rasters(raster_paths=outpaths, output_path=outpath)
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