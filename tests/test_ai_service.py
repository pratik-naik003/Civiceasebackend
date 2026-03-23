from app.services.ai.service import AIService


def test_priority_level_mapping():
    service = AIService()
    assert service._priority_level(0.9) == "p0"
    assert service._priority_level(0.7) == "p1"
    assert service._priority_level(0.5) == "p2"
    assert service._priority_level(0.2) == "p3"


def test_route_department_fallback_when_no_api_key():
    service = AIService()
    result = service.route_department(
        "overflowing garbage bins",
        [{"id": 1, "name": "Sanitation", "description": "waste and cleanliness"}],
    )
    assert result.department_name == "Sanitation"
    assert result.model == "fallback"
