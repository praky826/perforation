from backend.pipeline.phase0_ingestion.step01_raw_capture_ingestion import match_filename_to_tag


def test_capture_filename_tags_are_resolved():
    assert match_filename_to_tag("torch_1.CR3") == "torch_1"
    assert match_filename_to_tag("diffuse-overview.raw") == "diffuse"
    assert match_filename_to_tag("unclassified.raw") is None
