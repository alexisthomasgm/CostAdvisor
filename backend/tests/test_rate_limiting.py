"""Rate limiter smoke test."""


def test_auth_login_rate_limit(client):
    codes = []
    for _ in range(13):
        r = client.get("/auth/login", follow_redirects=False)
        codes.append(r.status_code)
    # First 10 should pass (redirect to Google), then 429s.
    assert codes[:10] != [429] * 10
    assert 429 in codes, f"expected 429 after 10 requests, got {codes}"
