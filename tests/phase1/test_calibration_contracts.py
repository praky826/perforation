import numpy as np

from backend.pipeline.phase1_calibration_registration.step02_lens_and_unit_calibration import undistort_frame
from backend.session.session_manager import SessionManager


def test_zero_distortion_preserves_frame_shape():
    frame = np.arange(16, dtype=np.float32).reshape(4, 4)
    corrected = undistort_frame(frame, [0.0, 0.0, 0.0])
    assert corrected.shape == frame.shape


def test_elevation_uses_session_calculation_contract():
    assert SessionManager.compute_elevation(10.0, 50.0, 0.0) == 11.31
