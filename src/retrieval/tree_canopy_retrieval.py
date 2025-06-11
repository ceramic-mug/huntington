"""
Gets from Meta's 1m map"""

import os
import rasterio
import geopandas as gpd
import numpy as np
from src.constants import *
import src.retrieval.utility as utility

def get_meta_tree_canopy(boundary = BOUNDARY_PATH, outpath = os.path.join(LAYER_DIR,'meta_tree_canopy_h.tif')):
    """
    Downloads 1m-resolution tree canopy heights from meta's global product
    Crops to boundary
    Merges if multiple tiles
    Deletes intermediate files, saving cropped and merged to outpath
    
    Details of Meta's product:
    https://www.sciencedirect.com/science/article/pii/S003442572300439X
    https://sustainability.atmeta.com/blog/2024/04/22/using-artificial-intelligence-to-map-the-earths-forests/
    
    """

    # Step 1: Find tile(s) that overlap boundary
    boundary = gpd.read_file(BOUNDARY_PATH)
    tiles = gpd.read_file(META_TILES_PATH)
    boundary.to_crs(tiles.crs, inplace = True)
    sj = gpd.sjoin(boundary, tiles, how="inner", predicate="intersects", lsuffix="left", rsuffix="right")
    tile_overlaps = sj['tile'].values
    
    # Step 2: Download corresponding data
    outpaths = []
    for t in tile_overlaps:
        outpath = os.path.join(LAYER_DIR,f'{t}.tif')
        if os.path.exists(outpath):
            continue
        os.system(f"aws s3 cp --no-sign-request s3://dataforgood-fb-data/forests/v1/alsgedi_global_v6_float/chm/{t}.tif {LAYER_DIR} --cli-read-timeout 0")
        outpaths.append(outpath)
    
    # Step 3: Crop and merge
    for o in outpaths:
        with open(o, 'rb') as f:
            out_image, out_meta = utility.crop_raster_with_shapefile(f, boundary)
        with open(o, 'wb') as f:
            if out_image is not None and out_meta is not None:
                output_filename = o
                with rasterio.open(output_filename, "w", **out_meta) as dest:
                    dest.write(out_image)

    utility.merge_rasters(outpaths, os.path.join(LAYER_DIR,'meta_tree_canopy_h.tif'))

    for o in outpaths:
        os.remove(o)

if __name__ == '__main__':
    get_meta_tree_canopy()