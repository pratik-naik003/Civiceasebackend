from conftest import set_current_user


def test_agent_creates_community_post(client, reporter_user):
    set_current_user(reporter_user)

    response = client.post(
        "/v1/agent/chat",
        json={"message": "create post title:Need clean park body:Please clean the central park this week"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_used"] == "create_post"
    assert payload["tool_result"]["post_id"] > 0


def test_agent_creates_resource_as_main_admin(client, main_admin_user):
    set_current_user(main_admin_user)

    response = client.post(
        "/v1/agent/chat",
        json={"message": "create resource title:Water Portal link:https://city.gov/water"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_used"] == "create_resource"
    assert payload["tool_result"]["resource_id"] > 0



def test_agent_lists_resources(client, main_admin_user):
    set_current_user(main_admin_user)

    client.post(
        "/v1/agent/chat",
        json={"message": "create resource title:Traffic Guide link:https://city.gov/traffic"},
    )

    response = client.post(
        "/v1/agent/chat",
        json={"message": "list resources"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_used"] == "list_resources"
    assert isinstance(payload["tool_result"], list)
    assert len(payload["tool_result"]) >= 1
