from conftest import set_current_user
from app.models.enums import UserRoleEnum
from app.models.user import UserRole


def test_resource_upload_flow(client, db_session, main_admin_user, reporter_user):
    set_current_user(main_admin_user)

    department_resp = client.post(
        "/v1/departments",
        json={"name": "Water Department", "description": "Water pipeline and leakage"},
    )
    assert department_resp.status_code == 201
    department_id = department_resp.json()["id"]

    # main admin can post municipality-wide resource (no department)
    global_resource_resp = client.post(
        "/v1/resources",
        json={
            "title": "Emergency Helpline",
            "link_url": "https://municipality.gov/helpline",
            "thumbnail_url": "https://municipality.gov/thumbs/helpline.png",
        },
    )
    assert global_resource_resp.status_code == 201
    assert global_resource_resp.json()["published_by"] == "Main Admin"
    assert global_resource_resp.json()["department_name"] is None

    # reporter alone cannot post without admin role
    set_current_user(reporter_user)
    forbidden_resp = client.post(
        "/v1/resources",
        json={
            "title": "Bad Attempt",
            "link_url": "https://example.com/resource",
            "department_id": department_id,
        },
    )
    assert forbidden_resp.status_code == 403

    # grant department admin role and post department-specific resource
    db_session.add(
        UserRole(user_id=reporter_user.id, role=UserRoleEnum.DEPARTMENT_ADMIN.value, department_id=department_id)
    )
    db_session.commit()

    dept_resource_resp = client.post(
        "/v1/resources",
        json={
            "title": "Water Complaint Guide",
            "link_url": "https://municipality.gov/water-guide",
            "thumbnail_url": "https://municipality.gov/thumbs/water-guide.png",
            "department_id": department_id,
        },
    )
    assert dept_resource_resp.status_code == 201
    assert dept_resource_resp.json()["department_name"] == "Water Department"
    assert dept_resource_resp.json()["published_by"] == "Water Department"

    list_resp = client.get("/v1/resources")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 2
