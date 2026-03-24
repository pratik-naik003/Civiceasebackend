from app.models.department import Department
from app.models.user import UserRole
from conftest import set_current_user


def test_create_issue_end_to_end(client, db_session, reporter_user, main_admin_user):
    set_current_user(main_admin_user)
    dep_response = client.post(
        "/v1/departments",
        json={"name": "Sanitation", "description": "Handles garbage and waste"},
    )
    assert dep_response.status_code == 201

    department_id = dep_response.json()["id"]

    db_session.add(UserRole(user_id=reporter_user.id, role="department_admin", department_id=department_id))
    db_session.commit()

    set_current_user(reporter_user)
    issue_response = client.post(
        "/v1/issues",
        json={
            "description": "Garbage is overflowing and smell is severe",
            "location": {"lat": 12.9716, "lng": 77.5946},
            "photo_key": "complaints/img1.jpg",
        },
    )
    assert issue_response.status_code == 201
    payload = issue_response.json()

    assert payload["department_id"] == department_id
    assert payload["priority_level"] in {"p0", "p1", "p2", "p3"}
    assert payload["cluster_id"] is not None
    assert payload["photo_keys"] == ["complaints/img1.jpg"]
    assert isinstance(payload["photo_urls"], list)

    my_issues = client.get("/v1/issues/me")
    assert my_issues.status_code == 200
    assert my_issues.json()["total"] == 1
    assert my_issues.json()["items"][0]["photo_keys"] == ["complaints/img1.jpg"]

    status_update = client.patch(f"/v1/issues/{payload['id']}/status", json={"status": "resolved"})
    assert status_update.status_code == 200
    assert status_update.json()["status"] == "resolved"
    assert status_update.json()["photo_keys"] == ["complaints/img1.jpg"]

    issue_detail = client.get(f"/v1/issues/{payload['id']}")
    assert issue_detail.status_code == 200
    assert issue_detail.json()["photo_keys"] == ["complaints/img1.jpg"]


def test_issue_image_upload_url(client, reporter_user):
    set_current_user(reporter_user)

    response = client.post("/v1/issues/images/upload-url", json={"file_name": "evidence.png"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["photo_key"] == "issues/evidence.png"
    assert "signed_upload_url" in payload
