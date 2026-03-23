from conftest import set_current_user


def test_community_discussion_flow(client, reporter_user):
    set_current_user(reporter_user)

    post_resp = client.post(
        "/v1/community/posts",
        json={
            "title": "Broken street near market",
            "body": "Road is unsafe and has huge potholes.",
            "image_keys": ["community/pothole1.jpg"],
        },
    )
    assert post_resp.status_code == 201
    post = post_resp.json()
    post_id = post["id"]
    assert post["score"] == 0

    vote_resp = client.post(f"/v1/community/posts/{post_id}/vote", json={"value": 1})
    assert vote_resp.status_code == 200
    assert vote_resp.json()["score"] == 1

    top_comment_resp = client.post(
        f"/v1/community/posts/{post_id}/comments",
        json={"body": "This is dangerous for school buses."},
    )
    assert top_comment_resp.status_code == 201
    top_comment = top_comment_resp.json()

    reply_resp = client.post(
        f"/v1/community/posts/{post_id}/comments",
        json={"body": "Agree, it needs urgent repair.", "parent_comment_id": top_comment["id"]},
    )
    assert reply_resp.status_code == 201

    c_vote_resp = client.post(f"/v1/community/comments/{top_comment['id']}/vote", json={"value": 1})
    assert c_vote_resp.status_code == 200
    assert c_vote_resp.json()["score"] == 1

    detail_resp = client.get(f"/v1/community/posts/{post_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["comment_count"] == 2
    assert len(detail["comments"]) == 1
    assert len(detail["comments"][0]["replies"]) == 1

    list_resp = client.get("/v1/community/posts?sort=top")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1
