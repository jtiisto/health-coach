"""Pytest configuration and fixtures for Coach tests."""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    db_path = tmp_path / "test_coach.db"
    yield db_path
    # Cleanup handled by tmp_path


@pytest.fixture(scope="function")
def test_app(temp_db_path, tmp_path, monkeypatch):
    """
    Create a test FastAPI app with isolated database.
    Uses monkeypatch to override DATABASE_PATH and PUBLIC_DIR.
    """
    # Create minimal public directory
    public_dir = tmp_path / "public"
    public_dir.mkdir()
    (public_dir / "index.html").write_text("<html><body>Test</body></html>")
    (public_dir / "styles.css").write_text("/* test */")

    js_dir = public_dir / "js"
    js_dir.mkdir()
    (js_dir / "app.js").write_text("// test")

    # Import and patch the server module
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    import server
    monkeypatch.setattr(server, "DATABASE_PATH", temp_db_path)
    monkeypatch.setattr(server, "PUBLIC_DIR", public_dir)

    # Initialize the database
    server.init_database()

    yield server.app


@pytest.fixture(scope="function")
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


@pytest.fixture
def sample_plan():
    """Sample workout plan for testing."""
    return {
        "day_name": "Test Workout",
        "location": "Home",
        "phase": "Foundation",
        "exercises": [
            {
                "id": "warmup_1",
                "name": "Stability Start",
                "type": "checklist",
                "items": ["Cat-Cow x10", "Bird-Dog x5/side"]
            },
            {
                "id": "ex_1",
                "name": "KB Goblet Squat",
                "type": "strength",
                "target_sets": 3,
                "target_reps": "10",
                "guidance_note": "Tempo 3-1-1"
            },
            {
                "id": "cardio_1",
                "name": "Zone 2 Bike",
                "type": "duration",
                "target_duration_min": 15,
                "guidance_note": "HR 135-148"
            }
        ]
    }


@pytest.fixture
def sample_log():
    """Sample workout log for testing."""
    return {
        "session_feedback": {
            "pain_discomfort": "None",
            "general_notes": "Good session"
        },
        "warmup_1": {
            "completed_items": ["Cat-Cow x10", "Bird-Dog x5/side"]
        },
        "ex_1": {
            "completed": True,
            "user_note": "Felt strong",
            "sets": [
                {"set_num": 1, "weight": 24, "reps": 10, "rpe": 7},
                {"set_num": 2, "weight": 24, "reps": 10, "rpe": 7.5},
                {"set_num": 3, "weight": 24, "reps": 10, "rpe": 8}
            ]
        },
        "cardio_1": {
            "completed": True,
            "duration_min": 16,
            "avg_hr": 142,
            "max_hr": 149
        }
    }
