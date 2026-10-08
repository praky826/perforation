import math

from backend.config.pipeline_constants import COMPOSITE_FIELD_ORDER
from backend.pipeline.phase3_feature_extraction.step18_composite_signature_assembly import assemble_vector


def test_composite_signature_has_frozen_field_order():
    vector = assemble_vector({
        "shape": {"mean_radius_um": 10.0, "roundness_ratio": None, "fourier_coeffs": [1, 2, 3, 4]},
        "roughness": {"sobel_mean": 5.0},
        "shadow": {"strength": 2.0, "direction_deg": 90.0},
    })

    assert len(vector) == len(COMPOSITE_FIELD_ORDER) == 14
    assert vector[:4] == [10.0, 0.0, 1.0, 2.0]
    assert math.isnan(vector[6])
    assert vector[-2:] == [2.0, 90.0]
