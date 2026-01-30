"""Integration tests for sync endpoints."""

import pytest
import json


@pytest.mark.integration
def test_workout_status_empty(client):
    """Test status endpoint with empty database."""
    response = client.get("/api/workout/status")
    assert response.status_code == 200
    data = response.json()
    assert "lastModified" in data


@pytest.mark.integration
def test_workout_sync_get_empty(client):
    """Test GET sync with empty database."""
    response = client.get("/api/workout/sync?client_id=test-client")
    assert response.status_code == 200
    data = response.json()
    assert data["plans"] == {}
    assert data["logs"] == {}
    assert "serverTime" in data


@pytest.mark.integration
def test_workout_sync_post_log(client, sample_log):
    """Test POST sync with a workout log."""
    response = client.post(
        "/api/workout/sync",
        json={
            "clientId": "test-client",
            "logs": {
                "2026-02-02": sample_log
            }
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "2026-02-02" in data["appliedLogs"]


@pytest.mark.integration
def test_workout_sync_roundtrip(client, sample_log):
    """Test uploading and then downloading a log."""
    # Upload
    client.post(
        "/api/workout/sync",
        json={
            "clientId": "test-client",
            "logs": {
                "2026-02-02": sample_log
            }
        }
    )

    # Download
    response = client.get("/api/workout/sync?client_id=test-client")
    data = response.json()

    assert "2026-02-02" in data["logs"]
    assert data["logs"]["2026-02-02"]["session_feedback"]["pain_discomfort"] == "None"


@pytest.mark.integration
def test_register_client(client):
    """Test client registration."""
    response = client.post(
        "/api/workout/register",
        params={"client_id": "test-client-123", "client_name": "Test Device"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["clientId"] == "test-client-123"
