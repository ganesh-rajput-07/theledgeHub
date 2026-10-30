def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health_reports_database_and_pgvector(client):
    body = client.get("/health").json()
    assert body["status"] == "healthy"
    assert body["database"] == "ok"
    assert body["pgvector"]
