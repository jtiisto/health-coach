"""Integration tests for MCP tools."""

import json
import pytest
import sqlite3
from datetime import datetime, timedelta


@pytest.mark.integration
class TestMCPConfig:
    def test_config_from_db_path(self, temp_db_path):
        """Should create config from database path."""
        from coach_mcp.config import MCPConfig

        # Create db first
        conn = sqlite3.connect(temp_db_path)
        conn.execute("CREATE TABLE test (id TEXT)")
        conn.close()

        config = MCPConfig.from_db_path(temp_db_path)
        assert config.db_path == temp_db_path
        assert config.max_rows == 1000

    def test_config_validation_missing_db(self, tmp_path):
        """Should raise error for missing database."""
        from coach_mcp.config import MCPConfig

        config = MCPConfig(db_path=tmp_path / "nonexistent.db")
        with pytest.raises(ValueError, match="Database file not found"):
            config.validate()

    def test_config_validation_invalid_max_rows(self, temp_db_path):
        """Should raise error for invalid max_rows."""
        from coach_mcp.config import MCPConfig

        # Create db first
        conn = sqlite3.connect(temp_db_path)
        conn.execute("CREATE TABLE test (id TEXT)")
        conn.close()

        config = MCPConfig(db_path=temp_db_path, max_rows=0)
        with pytest.raises(ValueError, match="max_rows must be at least 1"):
            config.validate()

    def test_config_validation_max_rows_exceeds_absolute(self, temp_db_path):
        """Should raise error when max_rows exceeds absolute limit."""
        from coach_mcp.config import MCPConfig

        conn = sqlite3.connect(temp_db_path)
        conn.execute("CREATE TABLE test (id TEXT)")
        conn.close()

        config = MCPConfig(db_path=temp_db_path, max_rows=10000, max_rows_absolute=5000)
        with pytest.raises(ValueError, match="cannot exceed"):
            config.validate()


@pytest.mark.integration
class TestDatabaseManager:
    def test_read_only_connection(self, mcp_config, db_manager):
        """Read-only connection should not allow writes."""
        # This should work (read)
        result = db_manager.execute_query("SELECT 1 as value", read_only=True)
        assert result[0]["value"] == 1

    def test_write_connection(self, mcp_config, db_manager):
        """Write connection should allow writes."""
        # Insert data
        db_manager.execute_write(
            "INSERT INTO workout_plans (date, plan_json, last_modified) VALUES (?, ?, ?)",
            ["2026-02-02", '{"test": true}', "2026-01-30T00:00:00Z"]
        )

        # Verify
        result = db_manager.execute_query("SELECT date FROM workout_plans")
        assert len(result) == 1
        assert result[0]["date"] == "2026-02-02"


@pytest.mark.integration
class TestSetWorkoutPlan:
    def test_create_plan(self, mcp_config, sample_plan):
        """Should create a new workout plan."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        # Call set_workout_plan
        result = tools["set_workout_plan"].fn(
            date="2026-02-02",
            plan=sample_plan
        )

        assert result["success"] is True
        assert result["date"] == "2026-02-02"
        assert result["plan"]["day_name"] == "Test Workout"

    def test_update_existing_plan(self, mcp_config, sample_plan):
        """Should update an existing plan."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        # Create plan
        tools["set_workout_plan"].fn(date="2026-02-02", plan=sample_plan)

        # Update plan
        updated_plan = {**sample_plan, "day_name": "Updated Workout"}
        result = tools["set_workout_plan"].fn(date="2026-02-02", plan=updated_plan)

        assert result["success"] is True
        assert result["plan"]["day_name"] == "Updated Workout"

    def test_plan_validation_missing_exercises(self, mcp_config):
        """Should reject plan without exercises."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        invalid_plan = {"day_name": "Test"}  # Missing exercises

        with pytest.raises(ValueError, match="missing required field"):
            tools["set_workout_plan"].fn(date="2026-02-02", plan=invalid_plan)

    def test_plan_validation_invalid_date(self, mcp_config, sample_plan):
        """Should reject invalid date format."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        with pytest.raises(ValueError, match="Invalid date format"):
            tools["set_workout_plan"].fn(date="02-02-2026", plan=sample_plan)

    def test_plan_validation_exercise_missing_id(self, mcp_config):
        """Should reject exercise without id."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        invalid_plan = {
            "day_name": "Test",
            "exercises": [{"name": "Squat", "type": "strength"}]  # Missing id
        }

        with pytest.raises(ValueError, match="missing 'id' field"):
            tools["set_workout_plan"].fn(date="2026-02-02", plan=invalid_plan)

    def test_plan_validation_invalid_exercise_type(self, mcp_config):
        """Should reject invalid exercise type."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        invalid_plan = {
            "day_name": "Test",
            "exercises": [{"id": "ex_1", "name": "Squat", "type": "invalid_type"}]
        }

        with pytest.raises(ValueError, match="invalid type"):
            tools["set_workout_plan"].fn(date="2026-02-02", plan=invalid_plan)


@pytest.mark.integration
class TestGetWorkoutPlan:
    def test_get_plans_empty(self, mcp_config):
        """Should return empty list for no plans."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        result = tools["get_workout_plan"].fn(
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        assert result == []

    def test_get_plans_with_data(self, mcp_config, sample_plan):
        """Should return plans within date range."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        # Create plans
        tools["set_workout_plan"].fn(date="2026-02-02", plan=sample_plan)
        tools["set_workout_plan"].fn(
            date="2026-02-04",
            plan={**sample_plan, "day_name": "Wednesday Workout"}
        )

        result = tools["get_workout_plan"].fn(
            start_date="2026-02-01",
            end_date="2026-02-05"
        )

        assert len(result) == 2
        dates = [p["date"] for p in result]
        assert "2026-02-02" in dates
        assert "2026-02-04" in dates

    def test_get_plans_date_filtering(self, mcp_config, sample_plan):
        """Should only return plans within specified range."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        # Create plans
        tools["set_workout_plan"].fn(date="2026-02-02", plan=sample_plan)
        tools["set_workout_plan"].fn(date="2026-02-09", plan=sample_plan)

        # Only request first week
        result = tools["get_workout_plan"].fn(
            start_date="2026-02-01",
            end_date="2026-02-07"
        )

        assert len(result) == 1
        assert result[0]["date"] == "2026-02-02"


@pytest.mark.integration
class TestGetWorkoutLogs:
    def test_get_logs_empty(self, mcp_config):
        """Should return empty list for no logs."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        result = tools["get_workout_logs"].fn(
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        assert result == []

    def test_get_logs_with_data(self, mcp_config, sample_log):
        """Should return logs within date range."""
        from coach_mcp.server import create_mcp_server, DatabaseManager

        db_manager = DatabaseManager(mcp_config)
        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        # Insert log directly
        now = datetime.utcnow().isoformat() + "Z"
        db_manager.execute_write(
            "INSERT INTO workout_logs (date, log_json, last_modified) VALUES (?, ?, ?)",
            ["2026-02-02", json.dumps(sample_log), now]
        )

        result = tools["get_workout_logs"].fn(
            start_date="2026-02-01",
            end_date="2026-02-05"
        )

        assert len(result) == 1
        assert result[0]["date"] == "2026-02-02"
        assert result[0]["log"]["session_feedback"]["pain_discomfort"] == "None"


@pytest.mark.integration
class TestGetWorkoutSummary:
    def test_summary_empty_database(self, mcp_config):
        """Should return summary with zero counts for empty database."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        result = tools["get_workout_summary"].fn(days=30)

        assert result["planned_workouts"] == 0
        assert result["completed_workouts"] == 0
        assert result["completion_rate_percent"] == 0

    def test_summary_with_data(self, mcp_config, sample_plan, sample_log):
        """Should return accurate summary with data."""
        from coach_mcp.server import create_mcp_server, DatabaseManager

        db_manager = DatabaseManager(mcp_config)
        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.utcnow().isoformat() + "Z"

        # Insert plan and log
        db_manager.execute_write(
            "INSERT INTO workout_plans (date, plan_json, last_modified) VALUES (?, ?, ?)",
            [today, json.dumps(sample_plan), now]
        )
        db_manager.execute_write(
            "INSERT INTO workout_logs (date, log_json, last_modified) VALUES (?, ?, ?)",
            [today, json.dumps(sample_log), now]
        )

        result = tools["get_workout_summary"].fn(days=30)

        assert result["planned_workouts"] == 1
        assert result["completed_workouts"] == 1
        assert result["completion_rate_percent"] == 100.0


@pytest.mark.integration
class TestListScheduledDates:
    def test_list_empty(self, mcp_config):
        """Should return empty list when no plans exist."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        result = tools["list_scheduled_dates"].fn()
        assert result == []

    def test_list_with_plans(self, mcp_config, sample_plan):
        """Should return dates with scheduled plans."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        # Create plans
        tools["set_workout_plan"].fn(date="2026-02-02", plan=sample_plan)
        tools["set_workout_plan"].fn(date="2026-02-04", plan=sample_plan)
        tools["set_workout_plan"].fn(date="2026-02-06", plan=sample_plan)

        result = tools["list_scheduled_dates"].fn(
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        assert len(result) == 3
        assert "2026-02-02" in result
        assert "2026-02-04" in result
        assert "2026-02-06" in result

    def test_list_respects_date_range(self, mcp_config, sample_plan):
        """Should only return dates within specified range."""
        from coach_mcp.server import create_mcp_server

        mcp = create_mcp_server(mcp_config)
        tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}

        # Create plans in different weeks
        tools["set_workout_plan"].fn(date="2026-02-02", plan=sample_plan)
        tools["set_workout_plan"].fn(date="2026-03-02", plan=sample_plan)

        result = tools["list_scheduled_dates"].fn(
            start_date="2026-02-01",
            end_date="2026-02-28"
        )

        assert len(result) == 1
        assert "2026-02-02" in result
        assert "2026-03-02" not in result
