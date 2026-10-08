"""IPDS Pipeline Constants and Configuration.

This module centralizes all tunable thresholds, constants, and ordering
definitions used across the 23-step IPDS computational pipeline and usability features.
Per project requirements, no threshold or constant may be hardcoded inline.
"""

from typing import Any, Dict, List, Tuple

# -------------------------------------------------------------------------
# Step 18: Fixed Composite Signature Field Ordering
# -------------------------------------------------------------------------
# Fixed session-wide ordering of the 14-element composite signature vector.
# Index i always corresponds to the exact same physical feature across all holes.
COMPOSITE_FIELD_ORDER: List[str] = [
    "mean_radius_um",          # Step 13: Average radius in microns
    "radius_std_um",           # Step 13: Point-to-point radius standard deviation (microns)
    "fourier_c1",              # Step 13: 1st harmonic Fourier coefficient magnitude
    "fourier_c2",              # Step 13: 2nd harmonic Fourier coefficient magnitude
    "fourier_c3",              # Step 13: 3rd harmonic Fourier coefficient magnitude
    "fourier_c4",              # Step 13: 4th harmonic Fourier coefficient magnitude
    "roundness_ratio",         # Step 13: 4*pi*area / perimeter^2 (NaN for edge teeth)
    "sobel_mean",              # Step 15: Mean boundary gradient magnitude
    "sobel_std",               # Step 15: Standard deviation of boundary gradient
    "glcm_contrast",           # Step 15: Gray-Level Co-occurrence Matrix contrast
    "glcm_homogeneity",        # Step 15: Gray-Level Co-occurrence Matrix homogeneity
    "residual_wobble",         # Step 15: High-frequency residual from Fourier fit
    "shadow_strength",         # Step 17: Combined shadow vector magnitude
    "shadow_direction_deg"     # Step 17: Dominant shadow angle (0 to 360 degrees)
]

# -------------------------------------------------------------------------
# Step 12 & 13: Geometric and Shape Extraction Settings
# -------------------------------------------------------------------------
RADIUS_PROFILE_NUM_ANGLES: int = 72       # 360 degrees sampled at 5-degree increments
FOURIER_FIT_ORDER: int = 4                # 1st through 4th harmonics for shape fitting

# -------------------------------------------------------------------------
# Step 4 & Feature 4: Illumination Matching and Calibration
# -------------------------------------------------------------------------
BRIGHTNESS_MISMATCH_TOLERANCE: float = 0.15   # +/- 15% brightness tolerance band
CAMERA_MATCH_KEYS: List[str] = [
    "aperture",
    "shutter_speed",
    "iso",
    "white_balance"
]

# -------------------------------------------------------------------------
# Step 14 & 15: Boundary Texture Sampling and Roughness Settings
# -------------------------------------------------------------------------
BOUNDARY_SAMPLE_SPACING_UM: float = 20.0   # Fixed physical arc-length spacing between boundary samples
BOUNDARY_PATCH_SIZE_PX: int = 7            # Square boundary patch side length in pixels (odd)
GLCM_LEVELS: int = 256                     # Gray levels for GLCM quantization (Step 15)
GLCM_DISTANCES: List[int] = [1]            # GLCM pixel-pair offset distances (Step 15)
GLCM_ANGLES_DEG: List[float] = [0.0]       # GLCM pixel-pair offset angles in degrees (Step 15)

# -------------------------------------------------------------------------
# Step 16: Angular Brightness Sampling Settings
# -------------------------------------------------------------------------
PAPER_SAMPLE_OFFSET_UM: float = 60.0       # Fixed radial offset outward onto paper beside the hole

# -------------------------------------------------------------------------
# Step 19: Reference Group Construction Settings
# -------------------------------------------------------------------------
MIN_HOLES_PER_EDGE: int = 5               # Minimum hole count on edge before pooling fallback

# -------------------------------------------------------------------------
# Step 20: Robust Statistics and Deviation Scoring
# -------------------------------------------------------------------------
MAD_SCALE_CONSTANT: float = 0.6745         # Consistency factor for normal distribution
COMBINATION_METHOD: str = "summed_z"       # Active combination: "summed_z" or "mahalanobis"

# -------------------------------------------------------------------------
# Step 21: Outlier Thresholding
# -------------------------------------------------------------------------
OUTLIER_CUTOFF: float = 3.0                # Robust z-score threshold for summed_z (typically 3.0 - 3.5)
MAHALANOBIS_SIGNIFICANCE_LEVEL: float = 0.025  # Chi-square tail probability for the mahalanobis cutoff

# -------------------------------------------------------------------------
# Step 22: Spatial Clustering and Candidate Region Localization
# -------------------------------------------------------------------------
REGION_MERGE_MAX_GAP: int = 1              # Bridge single non-flagged hole gaps in run
REGION_MERGE_ENABLED: bool = True          # Toggle for merging runs separated by one unflagged hole

# -------------------------------------------------------------------------
# Feature 26: Validation Mode ROC Cutoff Sweep
# -------------------------------------------------------------------------
VALIDATION_ROC_CUTOFF_MIN: float = 0.0     # Lowest cutoff in the ROC sweep
VALIDATION_ROC_CUTOFF_MAX: float = 6.0     # Highest cutoff in the ROC sweep
VALIDATION_ROC_CUTOFF_STEPS: int = 25      # Number of cutoff samples in the sweep

# -------------------------------------------------------------------------
# Feature 18: Suspicion Bands for Evidence-Framed Results Display
# -------------------------------------------------------------------------
# Suspicion level mapped from combined score distance relative to threshold:
# genuine: score <= threshold
# suspicious (low/med): threshold < score <= 2 * threshold
# highly_suspicious: score > 2 * threshold
SUSPICION_BANDS: Dict[str, Tuple[float, float]] = {
    "genuine": (0.0, 2.5),
    "suspicious": (2.5, 3.5),
    "highly_suspicious": (3.5, float("inf"))
}


def get_pipeline_constants_dict() -> Dict[str, Any]:
    """Return a full serializable snapshot of all pipeline constants for Feature 25."""
    return {
        "COMPOSITE_FIELD_ORDER": COMPOSITE_FIELD_ORDER,
        "RADIUS_PROFILE_NUM_ANGLES": RADIUS_PROFILE_NUM_ANGLES,
        "FOURIER_FIT_ORDER": FOURIER_FIT_ORDER,
        "BRIGHTNESS_MISMATCH_TOLERANCE": BRIGHTNESS_MISMATCH_TOLERANCE,
        "CAMERA_MATCH_KEYS": CAMERA_MATCH_KEYS,
        "BOUNDARY_SAMPLE_SPACING_UM": BOUNDARY_SAMPLE_SPACING_UM,
        "BOUNDARY_PATCH_SIZE_PX": BOUNDARY_PATCH_SIZE_PX,
        "GLCM_LEVELS": GLCM_LEVELS,
        "GLCM_DISTANCES": GLCM_DISTANCES,
        "GLCM_ANGLES_DEG": GLCM_ANGLES_DEG,
        "PAPER_SAMPLE_OFFSET_UM": PAPER_SAMPLE_OFFSET_UM,
        "MIN_HOLES_PER_EDGE": MIN_HOLES_PER_EDGE,
        "MAD_SCALE_CONSTANT": MAD_SCALE_CONSTANT,
        "COMBINATION_METHOD": COMBINATION_METHOD,
        "OUTLIER_CUTOFF": OUTLIER_CUTOFF,
        "MAHALANOBIS_SIGNIFICANCE_LEVEL": MAHALANOBIS_SIGNIFICANCE_LEVEL,
        "REGION_MERGE_MAX_GAP": REGION_MERGE_MAX_GAP,
        "REGION_MERGE_ENABLED": REGION_MERGE_ENABLED,
        "VALIDATION_ROC_CUTOFF_MIN": VALIDATION_ROC_CUTOFF_MIN,
        "VALIDATION_ROC_CUTOFF_MAX": VALIDATION_ROC_CUTOFF_MAX,
        "VALIDATION_ROC_CUTOFF_STEPS": VALIDATION_ROC_CUTOFF_STEPS,
        "SUSPICION_BANDS": {k: [v[0], v[1] if v[1] != float("inf") else "inf"] for k, v in SUSPICION_BANDS.items()}
    }
