import numpy as np
import pytest

from starfish import display, SegmentationMaskCollection
from starfish.core.test.factories import SyntheticData
from starfish.types import Coordinates


sd = SyntheticData(
    n_ch=2,
    n_round=3,
    n_spots=1,
    n_codes=4,
    n_photons_background=0,
    background_electrons=0,
    camera_detection_efficiency=1.0,
    gray_level=1,
    ad_conversion_bits=16,
    point_spread_function=(2, 2, 2),
)

stack = sd.spots()
spots = sd.intensities()
masks = SegmentationMaskCollection.from_label_image(
    np.random.rand(128, 128).astype(np.uint8),
    {Coordinates.Y: np.arange(128), Coordinates.X: np.arange(128)}
)


@pytest.mark.napari
@pytest.mark.parametrize('masks', [masks, None], ids=['masks', '     '])
@pytest.mark.parametrize('spots', [spots, None], ids=['spots', '     '])
@pytest.mark.parametrize('stack', [stack, None], ids=['stack', '     '])
def test_display(stack, spots, masks):
    import napari
    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QApplication

    def run():
        app = QApplication.instance() or QApplication([])
        viewer = napari.Viewer()
        timer = QTimer()
        timer.setInterval(500)
        timer.timeout.connect(viewer.window.close)
        timer.timeout.connect(app.quit)
        timer.start()
        display(stack, spots, masks, viewer=viewer)
        app.exec_()

    if stack is None and spots is None and masks is None:
        with pytest.raises(TypeError):
            run()
    else:
        run()
