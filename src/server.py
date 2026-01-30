"""
Coach Exercise Tracker Server - FastAPI backend with SQLite
Workout plan management and log synchronization
"""
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager, asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel


# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / "coach.db"
PUBLIC_DIR = PROJECT_ROOT / "public"

# Cache busting: unique version generated on each server start
SERVER_VERSION = uuid.uuid4().hex[:8]


@asynccontextmanager
async def lifespan(app):
    # Startup
    init_database()
    yield
    # Shutdown (nothing needed)


app = FastAPI(title="Coach Exercise Tracker Server", lifespan=lifespan)


# Database helpers
@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Initialize the database with required tables."""
    with get_db() as conn:
        cursor = conn.cursor()

        # workout_plans table - server-authoritative plans
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workout_plans (
                date TEXT PRIMARY KEY,
                plan_json TEXT NOT NULL,
                last_modified TEXT NOT NULL,
                last_modified_by TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_modified ON workout_plans(last_modified)")

        # workout_logs table - user workout logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workout_logs (
                date TEXT PRIMARY KEY,
                log_json TEXT NOT NULL,
                last_modified TEXT NOT NULL,
                last_modified_by TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_modified ON workout_logs(last_modified)")

        # clients table - track connected clients
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT,
                last_seen_at TEXT
            )
        """)

        # meta_sync table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meta_sync (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.commit()


def get_utc_now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.utcnow().isoformat() + "Z"


# Pydantic models
class WorkoutSyncPayload(BaseModel):
    clientId: str
    logs: dict[str, Any] = {}  # date -> log_json


class WorkoutSyncResponse(BaseModel):
    plans: dict[str, Any]  # date -> plan_json
    logs: dict[str, Any]   # date -> log_json
    serverTime: str


class StatusResponse(BaseModel):
    lastModified: Optional[str] = None


# API Endpoints
@app.get("/api/workout/status", response_model=StatusResponse)
def workout_status():
    """Get the last server sync time."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM meta_sync WHERE key = 'last_server_sync_time'")
        row = cursor.fetchone()

        if row:
            return StatusResponse(lastModified=row["value"])
        return StatusResponse(lastModified=None)


@app.post("/api/workout/register")
def register_client(client_id: str, client_name: Optional[str] = None):
    """Register or update a client."""
    with get_db() as conn:
        cursor = conn.cursor()
        now = get_utc_now()
        cursor.execute("""
            INSERT OR REPLACE INTO clients (id, name, last_seen_at)
            VALUES (?, ?, ?)
        """, (client_id, client_name or f"Client-{client_id[:8]}", now))
        conn.commit()
        return {"status": "ok", "clientId": client_id}


@app.get("/api/workout/sync", response_model=WorkoutSyncResponse)
def workout_sync_get(
    client_id: str = Query(...),
    last_sync_time: Optional[str] = Query(None)
):
    """
    Fetch workout plans and logs.
    If last_sync_time is provided, returns only changes since that time.
    Otherwise returns all data.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Update client last seen
        now = get_utc_now()
        cursor.execute("""
            UPDATE clients SET last_seen_at = ? WHERE id = ?
        """, (now, client_id))

        # Fetch plans
        if last_sync_time:
            cursor.execute("""
                SELECT date, plan_json, last_modified
                FROM workout_plans
                WHERE last_modified > ?
            """, (last_sync_time,))
        else:
            cursor.execute("SELECT date, plan_json, last_modified FROM workout_plans")

        plan_rows = cursor.fetchall()
        plans = {}
        for row in plan_rows:
            plan_data = json.loads(row["plan_json"])
            plan_data["_lastModified"] = row["last_modified"]
            plans[row["date"]] = plan_data

        # Fetch logs (last 30 days for full sync, or changes since last_sync_time)
        if last_sync_time:
            cursor.execute("""
                SELECT date, log_json, last_modified
                FROM workout_logs
                WHERE last_modified > ?
            """, (last_sync_time,))
        else:
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT date, log_json, last_modified
                FROM workout_logs
                WHERE date >= ?
            """, (thirty_days_ago,))

        log_rows = cursor.fetchall()
        logs = {}
        for row in log_rows:
            log_data = json.loads(row["log_json"])
            log_data["_lastModified"] = row["last_modified"]
            logs[row["date"]] = log_data

        conn.commit()
        return WorkoutSyncResponse(plans=plans, logs=logs, serverTime=now)


@app.post("/api/workout/sync")
def workout_sync_post(payload: WorkoutSyncPayload):
    """
    Upload workout logs from client.
    Uses last-write-wins strategy (no conflict detection).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        now = get_utc_now()
        client_id = payload.clientId

        # Update client last seen
        cursor.execute("""
            INSERT OR REPLACE INTO clients (id, name, last_seen_at)
            VALUES (?, ?, ?)
        """, (client_id, f"Client-{client_id[:8]}", now))

        applied_logs = {}

        # Process each log
        for date_str, log_data in payload.logs.items():
            log_json = json.dumps(log_data)

            cursor.execute("""
                INSERT OR REPLACE INTO workout_logs (date, log_json, last_modified, last_modified_by)
                VALUES (?, ?, ?, ?)
            """, (date_str, log_json, now, client_id))

            applied_logs[date_str] = log_data

        # Update server sync time
        cursor.execute("""
            INSERT OR REPLACE INTO meta_sync (key, value)
            VALUES ('last_server_sync_time', ?)
        """, (now,))

        conn.commit()

        return {
            "success": True,
            "appliedLogs": list(applied_logs.keys()),
            "serverTime": now
        }


# Static file serving
@app.get("/exercise")
def serve_exercise_app():
    """Serve the main index.html with cache-busting version injected."""
    index_path = PUBLIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")

    # Read and inject version into static file URLs
    html = index_path.read_text()
    html = html.replace('href="/styles.css"', f'href="/styles.css?v={SERVER_VERSION}"')
    html = html.replace('src="/js/app.js"', f'src="/js/app.js?v={SERVER_VERSION}"')

    return HTMLResponse(content=html)


@app.get("/styles.css")
def serve_css():
    """Serve the stylesheet with no-cache headers."""
    css_path = PUBLIC_DIR / "styles.css"
    if css_path.exists():
        return FileResponse(
            css_path,
            media_type="text/css",
            headers={"Cache-Control": "no-cache, must-revalidate"}
        )
    raise HTTPException(status_code=404, detail="styles.css not found")


@app.get("/js/{file_path:path}")
def serve_js(file_path: str):
    """Serve JavaScript files with no-cache headers."""
    js_path = PUBLIC_DIR / "js" / file_path
    if js_path.exists() and js_path.is_file():
        return FileResponse(
            js_path,
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache, must-revalidate"}
        )
    raise HTTPException(status_code=404, detail=f"JS file not found: {file_path}")


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Coach Exercise Tracker Server")
    parser.add_argument("--test", action="store_true", help="Run in testing mode (port 8003)")
    parser.add_argument("--port", type=int, help="Override the port number")
    args = parser.parse_args()

    port = args.port if args.port else (8003 if args.test else 8002)
    uvicorn.run(app, host="0.0.0.0", port=port)
