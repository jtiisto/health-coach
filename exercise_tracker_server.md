# Exercise Tracker Server Plan

## 1. Context & Goal
**Objective:** Extend the existing Journal Server (Python/FastAPI/SQLite) to support the Exercise Tracker.
**Constraint:** Must coexist with the Journal schema in `journal.db` (or a separate but linked structure).

## 2. Technical Stack
*   **Language:** Python 3.9+ (Same as Journal)
*   **Framework:** FastAPI
*   **Database:** SQLite (`journal.db`)
*   **ORM:** SQLAlchemy Core or Raw SQL (matching Journal style)

## 3. Core Responsibilities

### 3.1 Serving the PWA
*   Serve the new `exercise.html` (or similar entry point) and its specific static assets.

### 3.2 Plan Management (Server & MCP)
*   **Source of Truth:** The server stores the Master Plan in the database.
*   **Ingestion (MCP):** The MCP server exposes a **Read-Write** toolset for Plans.
    *   This allows an LLM to generate or update the 6-week plan (e.g., "Insert this workout for Feb 2nd").
    *   The LLM acts as the "Coach" configuring the database.
*   **Distribution (PWA):** The PWA fetches these plans.
*   **Conflict:** Plans are generally "Server Authoritative". PWA downloads them; it doesn't edit them.

### 3.3 Log Synchronization (Read/Write)
*   **Sync Logic:** Mirrors the Journal's `last_modified` / `dirty` logic.
*   **MCP Role:** **Read-Only** for Logs.
    *   Allows LLM to analyze performance (e.g., "Graph my squat volume").
    *   Does NOT allow the LLM to hallucinate fake workout logs.

## 4. Database Schema (Refined)

### 4.1 Table: `workout_plans`
*   `date` (TEXT, PK): ISO Date `YYYY-MM-DD`.
*   `plan_json` (TEXT): The full PWA-ready JSON structure for that day (containing exercises, guidance, targets).
*   `last_modified` (TEXT): Timestamp for sync.
*   *Note:* The MCP tool will accept a JSON structure and `INSERT OR REPLACE` into this table.

### 4.2 Table: `workout_logs`
*   `date` (TEXT, PK): ISO Date `YYYY-MM-DD`.
*   `log_json` (TEXT): The user's completed data.
*   `last_modified` (TEXT): Timestamp for sync.

## 5. API Endpoints
*   `GET /exercise` -> Serves the PWA.
*   `GET /api/workout/sync` -> Unified sync endpoint (simpler than split).
    *   **Params:** `last_sync_time`
    *   **Returns:**
        *   `plans`: New/Updated plans since `last_sync_time`.
        *   `logs`: New/Updated logs (if multi-device sync is needed, otherwise mostly an upload target).
*   `POST /api/workout/sync` -> Uploads dirty logs from client.

## 6. MCP Tool Definitions

### 6.1 `get_workout_logs`
*   **Input:** Date Range.
*   **Output:** JSON list of logs.
*   **Purpose:** Analysis.

### 6.2 `set_workout_plan`
*   **Input:** Date, Plan JSON Object.
*   **Output:** Success/Fail.
*   **Purpose:** Plan creation/adjustment by LLM.

### 6.3 `get_workout_plan`
*   **Input:** Date Range.
*   **Output:** JSON list of plans.
*   **Purpose:** Context for the LLM (e.g., "What is scheduled for tomorrow?").
