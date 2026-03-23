from app.services.ai.similarity import haversine_meters, text_similarity


def test_text_similarity_higher_for_related_texts():
    sim1 = text_similarity("garbage not collected near market", "garbage pile not collected at market road")
    sim2 = text_similarity("garbage not collected near market", "street light broken near school")
    assert sim1 > sim2


def test_haversine_is_small_for_nearby_points():
    distance = haversine_meters(12.9716, 77.5946, 12.9717, 77.5947)
    assert distance < 20
