from conftest import set_current_user


def test_users_me_returns_roles(client, reporter_user):
    set_current_user(reporter_user)

    response = client.get("/v1/users/me")
    assert response.status_code == 200

    payload = response.json()
    assert payload["id"] == reporter_user.id
    assert payload["firebase_uid"] == reporter_user.firebase_uid
    assert isinstance(payload["roles"], list)
    assert any(role["role"] == "reporter" for role in payload["roles"])
