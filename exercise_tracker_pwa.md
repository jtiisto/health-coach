# Exercise Tracker PWA Plan

## 1. Context & Architecture
**Base:** Built upon the existing Journal PWA architecture.
**Philosophy:** "No-Build" Mobile Web App (Offline First).
**Tech Stack:**
*   **Framework:** Preact (via ESM).
*   **Templating:** HTM.
*   **State:** Preact Signals.
*   **Persistence:** LocalForage (IndexedDB).
*   **Styling:** CSS Variables (matching Journal look & feel).

## 2. Core Features

### 2.1 Dynamic Workout Plans
*   The app does not hardcode the exercise plan.
*   It fetches **Plan Definitions** from the server.
*   Plans map specific Dates (or Week/Day patterns) to a list of Exercises.
*   **Offline Support:** Plan definitions are cached in LocalForage so the user can view today's workout even without internet.

### 2.2 Complex Exercise Tracking
Unlike the simple Journal (Checkboxes/Numbers), this requires structured data entry:
*   **Strength (Standard):** Variable Sets x Reps x Weight x RPE. (e.g., Set 1: 10x100lbs @ RPE 7).
*   **Weighted Duration:** Sets x Weight x Time (e.g., Farmer's Carry).
*   **Cardio (Steady State):** Total Duration + Manual HR Stats (Avg/Max) for Zone 2.
*   **Cardio (Interval/HIIT):** Rounds x (Work Time + Rest Time).
*   **Warm-up:** Dedicated checklist for "Stability Start" routines.

### 2.3 Notes System
*   **Guidance Note (Read-Only):** Comes from the Plan (e.g., "Tempo 3-1-1", "Rest until HR <= 130").
*   **User Note (Write):** Input field for the user to record specific feedback (e.g., "Knee felt weird", "Easy RPE").
*   **Session Feedback:** Global session fields for "Pain/Discomfort" (especially right knee) and general notes.

### 2.4 User Interface
*   **Daily View:** Shows the list of exercises for the selected date.
*   **Context:** Header indicates "Home" or "Gym" and Phase (e.g., "Foundation").
*   **Interaction:** Clicking an exercise expands it (Accordion style) or opens a focused modal.
*   **Input Area:** Inside the expanded view, dynamic rows for sets are generated based on the target.
*   **Special Actions:** Option to "Switch to Migraine Protocol" (fallback workout).

## 3. Data Models (Client-Side)

### 3.1 Store Structure (LocalForage)
*   `app_metadata`: Sync status, dirty flags.
*   `workout_plans`: Read-only definitions synced from server.
*   `workout_logs`: User's actual recorded data.

### 3.2 Schema: Workout Plan (Key: `workout_plans`)
*Stored as a map of Date -> List of Exercises*
```javascript
{
  "2026-02-02": {
    "day_name": "Lower Body + Bike",
    "location": "Home",
    "phase": "Foundation",
    "exercises": [
      {
        "id": "warmup_1",
        "name": "Stability Start",
        "type": "checklist",
        "items": ["Cat-Cow x10", "Bird-Dog x5/side", "Dead Bug x10", "Single-Leg Balance", "Thoracic Rotations", "Leg Swings"]
      },
      {
        "id": "ex_1",
        "name": "KB Goblet Squat",
        "type": "strength", // strength | weighted_time | duration | interval
        "target_sets": 3,
        "target_reps": "10",
        "guidance_note": "Tempo 3-1-1. Rest until HR <= 130."
      },
      {
        "id": "ex_2",
        "name": "Zone 2 Bike",
        "type": "duration",
        "target_duration_min": 15,
        "guidance_note": "HR 135-148. Log Avg/Max HR."
      }
    ]
  }
}
```

### 3.3 Schema: Workout Log (Key: `workout_logs`)
*Keyed by Date, then Exercise ID*
```javascript
{
  "2026-02-02": {
    "session_feedback": {
      "pain_discomfort": "Right knee felt tight on lunges",
      "migraine_protocol_used": false
    },
    "warmup_1": {
      "completed_items": ["Cat-Cow x10", "Bird-Dog x5/side", ...] 
    },
    "ex_1": {
      "completed": true,
      "user_note": "Felt strong, went heavy",
      "sets": [
        { "set_num": 1, "weight": 24, "reps": 10, "rpe": 7, "unit": "kg" },
        { "set_num": 2, "weight": 24, "reps": 10, "rpe": 7.5, "unit": "kg" }
      ]
    },
    "ex_2": {
      "completed": true,
      "duration_min": 16,
      "avg_hr": 142,
      "max_hr": 149
    }
  }
}
```

## 4. UI Layout Mockup

### Header
*   [Date Selector] (Similar to Journal, 7-day strip)
*   [Sync Indicator]

### Main Content (List)
*   **Heading:** "Lower Body Emphasis" (Foundation | Home)
*   **Warm-up:** [Stability Start] (Expandable checklist)
*   **List Item (Collapsed):**
    *   `KB Goblet Squat` | `3 x 10`
    *   [Checkbox] (Overall completion)
*   **List Item (Expanded):**
    *   **Header:** KB Goblet Squat
    *   **Guidance:** *Tempo 3-1-1. Rest until HR <= 130.*
    *   **Set 1:** [Input: 24 kg] [Input: 10 reps] [Input: RPE] [Check]
    *   **Set 2:** [Input: 24 kg] [Input: 10 reps] [Input: RPE] [Check]
    *   **User Note:** [Text Input]
*   **Session Feedback:**
    *   [Input: Pain/Discomfort Notes]
    
## 5. Sync Integration
*   **Downstream (Server -> Client):** Fetches `workout_plans` for the requested window.
*   **Upstream (Client -> Server):** Pushes `workout_logs` (only dirty days).
*   **Conflict Resolution:** Server is the source of truth for Plans. Client is the source of truth for Logs (last write wins logic for simple logging).
