from rasterio.merge import merge
import rasterio.mask

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