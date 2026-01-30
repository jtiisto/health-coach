"""Coach MCP Server implementation.

Provides access to workout plans (read-write) and logs (read-only)
through the Model Context Protocol for LLM workout planning and analysis.
"""

import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "FastMCP is required for MCP server functionality. "
        "Install with: pip install fastmcp"
    )

from .config import MCPConfig


class SQLiteConnection:
    """SQLite connection context manager with configurable read/write mode."""

    def __init__(self, db_path: Path, read_only: bool = True):
        self.db_path = db_path
        self.read_only = read_only
        self.conn = None

    def __enter__(self):
        """Open SQLite connection."""
        if self.read_only:
            self.conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        else:
            self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close connection safely."""
        if self.conn:
            self.conn.close()


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, config: MCPConfig):
        self.config = config

    def get_connection(self, read_only: bool = True):
        """Get database connection."""
        return SQLiteConnection(self.config.db_path, read_only=read_only)

    def execute_query(
        self, query: str, params: Optional[List[Any]] = None, read_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        try:
            with self.get_connection(read_only=read_only) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or [])
                if not read_only:
                    conn.commit()
                results = [dict(row) for row in cursor.fetchall()]
                return results
        except sqlite3.Error as e:
            raise ValueError(f"Database error: {str(e)}")

    def execute_write(
        self, query: str, params: Optional[List[Any]] = None
    ) -> int:
        """Execute a write query and return rows affected."""
        try:
            with self.get_connection(read_only=False) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or [])
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as e:
            raise ValueError(f"Database error: {str(e)}")


def get_utc_now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.utcnow().isoformat() + "Z"


def create_mcp_server(config: Optional[MCPConfig] = None) -> FastMCP:
    """Create and configure the Coach MCP server."""
    if config is None:
        if "COACH_DB_PATH" not in os.environ:
            raise ValueError("COACH_DB_PATH environment variable must be set")

        db_path = Path(os.environ["COACH_DB_PATH"])
        config = MCPConfig.from_db_path(db_path)

    config.validate()
    db_manager = DatabaseManager(config)
    mcp = FastMCP("Coach Workout Manager")

    @mcp.tool()
    def get_workout_plan(
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """WHEN TO USE: When you need to see what workouts are scheduled.

        Retrieves workout plans for the specified date range. Use this to:
        - Check what's scheduled for upcoming days
        - Review the structure of existing plans
        - Get context before creating new plans

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of plans with date and full plan structure including exercises
        """
        try:
            query = """
                SELECT date, plan_json, last_modified
                FROM workout_plans
                WHERE date >= ? AND date <= ?
                ORDER BY date
            """
            results = db_manager.execute_query(query, [start_date, end_date])

            plans = []
            for row in results:
                plan_data = json.loads(row["plan_json"])
                plans.append({
                    "date": row["date"],
                    "last_modified": row["last_modified"],
                    "plan": plan_data
                })

            return plans
        except Exception as e:
            raise ValueError(f"Failed to get workout plans: {str(e)}")

    @mcp.tool()
    def get_workout_logs(
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """WHEN TO USE: When analyzing workout history or performance trends.

        Retrieves completed workout logs for the specified date range. Use this to:
        - Review what exercises were actually completed
        - Analyze performance data (weights, reps, RPE)
        - Track progress over time
        - Identify patterns in workout adherence

        This is READ-ONLY - logs are created by the user through the PWA.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of logs with date and exercise completion data
        """
        try:
            query = """
                SELECT date, log_json, last_modified
                FROM workout_logs
                WHERE date >= ? AND date <= ?
                ORDER BY date
            """
            results = db_manager.execute_query(query, [start_date, end_date])

            logs = []
            for row in results:
                log_data = json.loads(row["log_json"])
                logs.append({
                    "date": row["date"],
                    "last_modified": row["last_modified"],
                    "log": log_data
                })

            return logs
        except Exception as e:
            raise ValueError(f"Failed to get workout logs: {str(e)}")

    @mcp.tool()
    def set_workout_plan(
        date: str,
        plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """WHEN TO USE: When creating or updating a workout plan for a specific date.

        Creates or replaces the workout plan for the given date. Use this to:
        - Schedule new workouts
        - Update existing plans
        - Build out a multi-week training program

        The plan should follow the structured format with exercises defined.

        Args:
            date: Target date (YYYY-MM-DD)
            plan: Plan object with the following structure:
                {
                    "day_name": "Lower Body + Bike",
                    "location": "Home" or "Gym",
                    "phase": "Foundation" or "Building" or "Intensity",
                    "exercises": [
                        {
                            "id": "unique_id",
                            "name": "Exercise Name",
                            "type": "strength" | "duration" | "checklist" | "weighted_time" | "interval",
                            "target_sets": 3,  # for strength
                            "target_reps": "10" or "8-10",  # for strength
                            "target_duration_min": 15,  # for duration/cardio
                            "items": ["item1", "item2"],  # for checklist
                            "guidance_note": "Tempo 3-1-1. Rest until HR <= 130."
                        }
                    ]
                }

        Returns:
            Success confirmation with the saved plan

        Example:
            set_workout_plan("2026-02-02", {
                "day_name": "Lower Body + Bike",
                "location": "Home",
                "phase": "Foundation",
                "exercises": [
                    {"id": "warmup_1", "name": "Stability Start", "type": "checklist",
                     "items": ["Cat-Cow x10", "Bird-Dog x5/side", "Dead Bug x10"]},
                    {"id": "ex_1", "name": "KB Goblet Squat", "type": "strength",
                     "target_sets": 3, "target_reps": "10", "guidance_note": "Tempo 3-1-1"}
                ]
            })
        """
        # Validate date format
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: {date}. Use YYYY-MM-DD")

        # Validate plan structure
        if not isinstance(plan, dict):
            raise ValueError("Plan must be a dictionary")

        required_fields = ["day_name", "exercises"]
        for field in required_fields:
            if field not in plan:
                raise ValueError(f"Plan missing required field: {field}")

        if not isinstance(plan["exercises"], list):
            raise ValueError("Plan exercises must be a list")

        # Validate each exercise has required fields
        for i, exercise in enumerate(plan["exercises"]):
            if "id" not in exercise:
                raise ValueError(f"Exercise {i} missing 'id' field")
            if "name" not in exercise:
                raise ValueError(f"Exercise {i} missing 'name' field")
            if "type" not in exercise:
                raise ValueError(f"Exercise {i} missing 'type' field")

            valid_types = ["strength", "duration", "checklist", "weighted_time", "interval", "circuit"]
            if exercise["type"] not in valid_types:
                raise ValueError(f"Exercise {i} has invalid type: {exercise['type']}. Must be one of: {valid_types}")

        try:
            now = get_utc_now()
            plan_json = json.dumps(plan)

            query = """
                INSERT OR REPLACE INTO workout_plans (date, plan_json, last_modified, last_modified_by)
                VALUES (?, ?, ?, ?)
            """
            db_manager.execute_write(query, [date, plan_json, now, "mcp"])

            return {
                "success": True,
                "date": date,
                "last_modified": now,
                "plan": plan,
                "message": f"Workout plan for {date} saved successfully"
            }
        except Exception as e:
            raise ValueError(f"Failed to save workout plan: {str(e)}")

    @mcp.tool()
    def get_workout_summary(days: int = 30) -> Dict[str, Any]:
        """WHEN TO USE: When you want a quick overview of workout activity.

        Provides summary statistics about workout plans and completed logs.

        Args:
            days: Number of recent days to analyze (max 365, default: 30)

        Returns:
            Summary including planned vs completed workouts, exercise counts, etc.
        """
        if days > 365:
            raise ValueError("Days cannot exceed 365")

        try:
            start_date = (date.today() - timedelta(days=days)).isoformat()
            end_date = date.today().isoformat()

            # Count planned workouts
            plans_query = """
                SELECT COUNT(*) as count FROM workout_plans
                WHERE date >= ? AND date <= ?
            """
            plans_result = db_manager.execute_query(plans_query, [start_date, end_date])
            planned_count = plans_result[0]["count"] if plans_result else 0

            # Count completed workouts (logs exist)
            logs_query = """
                SELECT COUNT(*) as count FROM workout_logs
                WHERE date >= ? AND date <= ?
            """
            logs_result = db_manager.execute_query(logs_query, [start_date, end_date])
            completed_count = logs_result[0]["count"] if logs_result else 0

            # Get recent plans
            recent_plans_query = """
                SELECT date, plan_json FROM workout_plans
                WHERE date >= ? AND date <= ?
                ORDER BY date DESC
                LIMIT 7
            """
            recent_plans = db_manager.execute_query(recent_plans_query, [start_date, end_date])

            # Parse exercise counts from plans
            exercise_types = {}
            for row in recent_plans:
                plan = json.loads(row["plan_json"])
                for ex in plan.get("exercises", []):
                    ex_type = ex.get("type", "unknown")
                    exercise_types[ex_type] = exercise_types.get(ex_type, 0) + 1

            completion_rate = round(completed_count / planned_count * 100, 1) if planned_count > 0 else 0

            return {
                "analysis_period_days": days,
                "planned_workouts": planned_count,
                "completed_workouts": completed_count,
                "completion_rate_percent": completion_rate,
                "exercise_types_in_recent_plans": exercise_types,
                "recent_plan_dates": [row["date"] for row in recent_plans]
            }
        except Exception as e:
            raise ValueError(f"Failed to generate summary: {str(e)}")

    @mcp.tool()
    def list_scheduled_dates(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[str]:
        """WHEN TO USE: When you need to see which dates have plans scheduled.

        Returns a list of dates that have workout plans. Useful for:
        - Checking what's already scheduled before adding new plans
        - Finding gaps in the training schedule
        - Planning around existing workouts

        Args:
            start_date: Start date (YYYY-MM-DD), defaults to today
            end_date: End date (YYYY-MM-DD), defaults to 6 weeks from today

        Returns:
            List of dates (YYYY-MM-DD) that have plans
        """
        try:
            if not start_date:
                start_date = date.today().isoformat()
            if not end_date:
                end_date = (date.today() + timedelta(weeks=6)).isoformat()

            query = """
                SELECT date FROM workout_plans
                WHERE date >= ? AND date <= ?
                ORDER BY date
            """
            results = db_manager.execute_query(query, [start_date, end_date])

            return [row["date"] for row in results]
        except Exception as e:
            raise ValueError(f"Failed to list scheduled dates: {str(e)}")

    @mcp.resource("file://coach_plan_guide")
    def coach_plan_guide() -> str:
        """Complete guide to creating workout plans."""
        return _get_coach_plan_guide()

    return mcp


def _get_coach_plan_guide() -> str:
    """Get comprehensive guide for creating workout plans."""
    return """
# Coach Workout Plan Guide

## Quick Start
1. Use `list_scheduled_dates` to see what's already planned
2. Use `get_workout_plan` to see existing plan structures
3. Use `set_workout_plan` to create new plans
4. Use `get_workout_logs` to analyze past performance

## Plan Structure

Each workout plan has:
- `day_name`: Description of the workout focus (e.g., "Lower Body + Bike")
- `location`: "Home" or "Gym"
- `phase`: Training phase ("Foundation", "Building", "Intensity")
- `exercises`: Array of exercise definitions

## Exercise Types

### strength
For weight training exercises with sets/reps.
```json
{
    "id": "ex_1",
    "name": "KB Goblet Squat",
    "type": "strength",
    "target_sets": 3,
    "target_reps": "10",
    "guidance_note": "Tempo 3-1-1. Rest until HR <= 130."
}
```

### duration
For cardio with time-based goals.
```json
{
    "id": "cardio_1",
    "name": "Zone 2 Bike",
    "type": "duration",
    "target_duration_min": 15,
    "guidance_note": "HR 135-148. Log Avg/Max HR."
}
```

### checklist
For warm-ups or routines with multiple items.
```json
{
    "id": "warmup_1",
    "name": "Stability Start",
    "type": "checklist",
    "items": ["Cat-Cow x10", "Bird-Dog x5/side", "Dead Bug x10"]
}
```

### weighted_time
For exercises with weight and duration (e.g., carries).
```json
{
    "id": "ex_5",
    "name": "Farmer's Carry",
    "type": "weighted_time",
    "target_duration_sec": 60,
    "guidance_note": "Heavy weight, maintain posture"
}
```

### interval
For HIIT or interval training.
```json
{
    "id": "hiit_1",
    "name": "Bike Intervals",
    "type": "interval",
    "rounds": 4,
    "work_duration_sec": 30,
    "rest_duration_sec": 90,
    "guidance_note": "All-out effort on work intervals"
}
```

## Best Practices

1. **Unique IDs**: Each exercise needs a unique `id` within the plan
2. **Guidance Notes**: Include tempo, rest periods, HR targets
3. **Progressive Overload**: Increase volume/intensity across phases
4. **Rest Guidance**: Include HR-based rest recommendations for strength work

## Example: Full Workout Plan

```json
{
    "day_name": "Lower Body + Conditioning",
    "location": "Home",
    "phase": "Foundation",
    "exercises": [
        {
            "id": "warmup_1",
            "name": "Stability Start",
            "type": "checklist",
            "items": [
                "Cat-Cow x10",
                "Bird-Dog x5/side",
                "Dead Bug x10",
                "Single-Leg Balance 30s/side"
            ]
        },
        {
            "id": "ex_1",
            "name": "KB Goblet Squat",
            "type": "strength",
            "target_sets": 3,
            "target_reps": "10",
            "guidance_note": "Tempo 3-1-1. Rest until HR <= 130."
        },
        {
            "id": "ex_2",
            "name": "DB Romanian Deadlift",
            "type": "strength",
            "target_sets": 3,
            "target_reps": "10",
            "guidance_note": "Tempo 3-1-1. Feel hamstring stretch."
        },
        {
            "id": "cardio_1",
            "name": "Zone 2 Bike",
            "type": "duration",
            "target_duration_min": 15,
            "guidance_note": "HR 135-148. Log Avg/Max HR."
        }
    ]
}
```
    """.strip()


def main():
    """Main entry point for the Coach MCP server."""
    try:
        mcp = create_mcp_server()
        mcp.run()
    except Exception as e:
        print(f"Failed to start MCP server: {e}")
        raise


if __name__ == "__main__":
    main()
