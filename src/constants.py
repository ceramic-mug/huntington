import os

LAYER_DIR = 'layers'

if not os.path.exists(LAYER_DIR):
    os.makedirs(LAYER_DIR)

BOUNDARY_PATH = os.path.join('boundaries','huntington_2024_tigerline.shp')
META_TILES_PATH = os.path.join('src','retrieval','helper_files','tiles.geojson')