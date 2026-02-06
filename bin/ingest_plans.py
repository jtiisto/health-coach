#!/usr/bin/env python3
"""Ingest exercise plans from JSON file into database via MCP tools."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from coach_mcp.config import MCPConfig
from coach_mcp.server import create_mcp_server, _transform_block_plan


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <plans.json>")
        sys.exit(1)

    json_path = Path(sys.argv[1])

    if not json_path.exists():
        print(f"Error: {json_path} not found")
        sys.exit(1)

    with open(json_path) as f:
        all_plans = json.load(f)

    print(f"Loaded {len(all_plans)} workout plans from {json_path}")

    # Initialize MCP with database
    db_path = Path(__file__).parent.parent / "coach.db"

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        print("Run the server first to initialize the database: python src/server.py")
        sys.exit(1)

    config = MCPConfig(db_path=db_path)
    mcp = create_mcp_server(config)

    # Get the set_workout_plan tool function
    tools = {tool.name: tool for tool in mcp._tool_manager._tools.values()}
    set_plan = tools["set_workout_plan"].fn

    # Ingest each plan
    success_count = 0
    error_count = 0

    for date_str, plan_data in sorted(all_plans.items()):
        try:
            # Transform to MCP format
            transformed = _transform_block_plan(plan_data)

            # Call MCP tool
            result = set_plan(date=date_str, plan=transformed)

            if result.get("success"):
                print(f"  {date_str}: {transformed['day_name']} ({len(transformed['exercises'])} exercises)")
                success_count += 1
            else:
                print(f"  {date_str}: FAILED - {result}")
                error_count += 1

        except Exception as e:
            print(f"  {date_str}: ERROR - {str(e)}")
            error_count += 1

    print(f"\nComplete: {success_count} plans ingested, {error_count} errors")


if __name__ == "__main__":
    main()
