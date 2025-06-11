import os
from src.retrieval import dem_retrieval
from src.constants import *

if __name__ == '__main__':
    dem_retrieval.get_dem(
        boundary_path=BOUNDARY_PATH,
        outpath=os.path.join(LAYER_DIR, '30m_dem.tif'),
        resolution='30m',
        crop=True
    )