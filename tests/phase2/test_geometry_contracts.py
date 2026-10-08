from backend.pipeline.phase2_geometry_classification.step08_hole_tooth_classification import classify_hole_type


def test_hole_classification_distinguishes_interior_and_edge():
    boundary = [[0, 0], [100, 0], [100, 100], [0, 100]]
    interior = [[45, 45], [55, 45], [55, 55], [45, 55]]
    edge = [[0, 45], [5, 45], [5, 55], [0, 55]]

    assert classify_hole_type(interior, boundary) == "interior_hole"
    assert classify_hole_type(edge, boundary) == "edge_tooth"
