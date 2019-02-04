from typing import Collection, Mapping, MutableSequence, Optional, Tuple, Union

import numpy as np

from starfish.imagestack.parser import TileCollectionData, TileData, TileKey
from starfish.imagestack.physical_coordinate_calculator import recalculate_physical_coordinate_range
from starfish.types import Axes, Coordinates, Number


class CropParameters:
    """Parameters for cropping an ImageStack at load time."""
    def __init__(
            self,
            *,
            permitted_rounds: Optional[Collection[int]]=None,
            permitted_chs: Optional[Collection[int]]=None,
            permitted_zplanes: Optional[Collection[int]]=None,
            x_slice: Optional[Union[int, slice]]=None,
            y_slice: Optional[Union[int, slice]]=None,
    ):
        """
        Parameters
        ----------
        permitted_rounds : Optional[Collection[int]]
            The rounds in the original dataset to load into the ImageStack.  If this is not set,
            then all rounds are loaded into the ImageStack.
        permitted_chs : Optional[Collection[int]]
            The channels in the original dataset to load into the ImageStack.  If this is not set,
            then all channels are loaded into the ImageStack.
        permitted_zplanes : Optional[Collection[int]]
            The z-layers in the original dataset to load into the ImageStack.  If this is not set,
            then all z-layers are loaded into the ImageStack.
        x_slice : Optional[Union[int, slice]]
            The x-range in the x-y tile that is loaded into the ImageStack.  If this is not set,
            then the entire x-y tile is loaded into the ImageStack.
        y_slice : Optional[Union[int, slice]]
            The y-range in the x-y tile that is loaded into the ImageStack.  If this is not set,
            then the entire x-y tile is loaded into the ImageStack.
        """
        self._permitted_rounds = set(permitted_rounds) if permitted_rounds else None
        self._permitted_chs = set(permitted_chs) if permitted_chs else None
        self._permitted_zplanes = set(permitted_zplanes) if permitted_zplanes else None
        self._x_slice = x_slice
        self._y_slice = y_slice

    def __repr__(self):
        return (f"<starfish.CropParameters>"
                f"  Rounds: {self._permitted_rounds}"
                f"  Channels: {self._permitted_chs}"
                f"  Z_PLanes: {self._permitted_zplanes}"
                f"  X_Slice: {self._x_slice}"
                f"  Y_Slice: {self._y_slice}"
                )

    def filter_tilekeys(self, tilekeys: Collection[TileKey]) -> Collection[TileKey]:
        """
        Filters tilekeys for those that should be included in the resulting ImageStack.
        """
        results: MutableSequence[TileKey] = list()
        for tilekey in tilekeys:
            if self._permitted_rounds is not None and tilekey.round not in self._permitted_rounds:
                continue
            if self._permitted_chs is not None and tilekey.ch not in self._permitted_chs:
                continue
            if self._permitted_zplanes is not None and tilekey.z not in self._permitted_zplanes:
                continue

            results.append(tilekey)

        return results

    @staticmethod
    def _crop_axis(size: int, crop: Optional[Union[int, slice]]) -> Tuple[int, int]:
        """
        Given the size of along an axis, and an optional cropping, return the start index
        (inclusive) and end index (exclusive) of the crop.  If no crop is specified, then the
        original size (0, size) is returned.
        """
        # convert int crops to a slice operation.
        if isinstance(crop, int):
            if crop < 0 or crop >= size:
                raise IndexError("crop index out of range")
            return crop, crop + 1

        # convert start and stop to absolute values.
        start: int
        if crop is None or crop.start is None:
            start = 0
        elif crop.start is not None and crop.start < 0:
            start = max(0, size + crop.start)
        else:
            start = min(size, crop.start)

        stop: int
        if crop is None or crop.stop is None:
            stop = size
        elif crop.stop is not None and crop.stop < 0:
            stop = max(0, size + crop.stop)
        else:
            stop = min(size, crop.stop)

        return start, stop

    def crop_shape(self, shape: Tuple[int, int]) -> Tuple[int, int]:
        """
        Given the shape of the original tile, return the shape of the cropped tile.
        """
        output_x_shape = CropParameters._crop_axis(shape[1], self._x_slice)
        output_y_shape = CropParameters._crop_axis(shape[0], self._y_slice)
        width = output_x_shape[1] - output_x_shape[0]
        height = output_y_shape[1] - output_y_shape[0]

        return height, width

    def crop_image(self, image: np.ndarray) -> np.ndarray:
        """
        Given the original image, return the cropped image.
        """
        output_x_shape = CropParameters._crop_axis(image.shape[1], self._x_slice)
        output_y_shape = CropParameters._crop_axis(image.shape[0], self._y_slice)

        return image[output_y_shape[0]:output_y_shape[1], output_x_shape[0]:output_x_shape[1]]

    def crop_coordinates(
            self,
            coordinates: Mapping[Coordinates, Tuple[Number, Number]],
            shape: Tuple[int, int],
    ) -> Mapping[Coordinates, Tuple[Number, Number]]:
        """
        Given a mapping of coordinate to coordinate values, return a mapping of the coordinate to
        cropped coordinate values.
        """
        xmin, xmax = coordinates[Coordinates.X]
        ymin, ymax = coordinates[Coordinates.Y]
        if self._x_slice is not None:
            xmin, xmax = recalculate_physical_coordinate_range(
                xmin, xmax,
                shape[1],
                self._x_slice)
        if self._y_slice is not None:
            ymin, ymax = recalculate_physical_coordinate_range(
                ymin, ymax,
                shape[0],
                self._y_slice)

        return {
            Coordinates.X: (xmin, xmax),
            Coordinates.Y: (ymin, ymax),
            Coordinates.Z: coordinates[Coordinates.Z],
        }


class CroppedTileData(TileData):
    """Represent a cropped view of a TileData object."""
    def __init__(self, tile_data: TileData, cropping_parameters: CropParameters):
        self.backing_tile_data = tile_data
        self.cropping_parameters = cropping_parameters

    @property
    def tile_shape(self) -> Tuple[int, int]:
        return self.cropping_parameters.crop_shape(self.backing_tile_data.tile_shape)

    @property
    def numpy_array(self) -> np.ndarray:
        return self.cropping_parameters.crop_image(self.backing_tile_data.numpy_array)

    @property
    def coordinates(self) -> Mapping[Coordinates, Tuple[Number, Number]]:
        return self.cropping_parameters.crop_coordinates(
            self.backing_tile_data.coordinates,
            self.backing_tile_data.tile_shape,
        )

    @property
    def selector(self) -> Mapping[Axes, int]:
        return self.backing_tile_data.selector


class CroppedTileCollectionData(TileCollectionData):
    """Represent a cropped view of a TileCollectionData object."""
    def __init__(
            self,
            backing_tile_collection_data: TileCollectionData,
            crop_parameters: CropParameters,
    ) -> None:
        self.backing_tile_collection_data = backing_tile_collection_data
        self.crop_parameters = crop_parameters

    def __getitem__(self, tilekey: TileKey) -> dict:
        return self.backing_tile_collection_data[tilekey]

    def keys(self) -> Collection[TileKey]:
        return self.crop_parameters.filter_tilekeys(self.backing_tile_collection_data.keys())

    @property
    def extras(self) -> dict:
        return self.backing_tile_collection_data.extras

    def get_tile_by_key(self, tilekey: TileKey) -> TileData:
        return CroppedTileData(
            self.backing_tile_collection_data.get_tile_by_key(tilekey),
            self.crop_parameters,
        )

    def get_tile(self, r: int, ch: int, z: int) -> TileData:
        return CroppedTileData(
            self.backing_tile_collection_data.get_tile(r, ch, z),
            self.crop_parameters,
        )
