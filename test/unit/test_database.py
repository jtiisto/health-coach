"""Unit tests for database initialization."""

import pytest
import sqlite3


@pytest.mark.unit
def test_database_tables_created(test_app, temp_db_path):
    """Test that all required tables are created."""
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    conn.close()

    assert "workout_plans" in tables
    assert "workout_logs" in tables
    assert "clients" in tables
    assert "meta_sync" in tables


@pytest.mark.unit
def test_workout_plans_schema(test_app, temp_db_path):
    """Test workout_plans table schema."""
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(workout_plans)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    conn.close()

    assert "date" in columns
    assert "plan_json" in columns
    assert "last_modified" in columns
    assert "last_modified_by" in columns


@pytest.mark.unit
def test_workout_logs_schema(test_app, temp_db_path):
    """Test workout_logs table schema."""
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(workout_logs)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    conn.close()

    assert "date" in columns
    assert "log_json" in columns
    assert "last_modified" in columns
    assert "last_modified_by" in columns
