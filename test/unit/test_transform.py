"""Tests for _transform_block_to_exercises and _is_bodyweight_or_band."""

import pytest

from coach_mcp.server import _is_bodyweight_or_band, _transform_block_to_exercises


# --- rounds parsing ---

def _make_circuit_block(exercises, rest_guidance="", block_type="circuit", rounds=None):
    block = {
        "block_type": block_type,
        "title": "Test Block",
        "rest_guidance": rest_guidance,
        "exercises": exercises,
    }
    if rounds is not None:
        block["rounds"] = rounds
    return block


class TestRoundsParsing:
    def test_circuit_4_rounds(self):
        block = _make_circuit_block(
            [{"name": "KB Swings", "reps": 10}],
            rounds=4,
        )
        results = _transform_block_to_exercises(block, 0)
        assert results[0]["target_sets"] == 4

    def test_power_block_rounds(self):
        block = _make_circuit_block(
            [{"name": "Box Jump", "reps": 5}],
            rounds=5,
            block_type="power",
        )
        results = _transform_block_to_exercises(block, 0)
        assert results[0]["target_sets"] == 5

    def test_no_rounds_no_target_sets(self):
        block = _make_circuit_block(
            [{"name": "KB Swings", "reps": 10}],
        )
        results = _transform_block_to_exercises(block, 0)
        assert "target_sets" not in results[0]

    def test_explicit_sets_override_rounds(self):
        block = _make_circuit_block(
            [{"name": "KB Swings", "reps": 10, "sets": 2}],
            rounds=4,
        )
        results = _transform_block_to_exercises(block, 0)
        assert results[0]["target_sets"] == 2


# --- hide_weight ---

class TestHideWeight:
    @pytest.mark.parametrize("name", [
        "Push-ups",
        "Band Pull-Aparts",
        "Bodyweight Squat Hold",
        "Banded Face Pulls",
        "Jump Squat",
        "Plank Hold",
        "Dead Hang",
        "Wall Sit",
        "Glute Bridge",
    ])
    def test_bodyweight_or_band_exercises_hidden(self, name):
        block = _make_circuit_block([{"name": name, "reps": 10}])
        results = _transform_block_to_exercises(block, 0)
        assert results[0].get("hide_weight") is True

    @pytest.mark.parametrize("name", [
        "KB Swings",
        "Farmer's Carry",
        "Dumbbell Row",
        "Barbell Squat",
    ])
    def test_weighted_exercises_not_hidden(self, name):
        block = _make_circuit_block([{"name": name, "reps": 10}])
        results = _transform_block_to_exercises(block, 0)
        assert "hide_weight" not in results[0]

    def test_hide_weight_applies_to_strength_block(self):
        block = {
            "block_type": "strength",
            "title": "Strength",
            "rest_guidance": "",
            "exercises": [{"name": "Push-ups", "reps": 10}],
        }
        results = _transform_block_to_exercises(block, 0)
        assert results[0].get("hide_weight") is True


# --- guidance_note includes rest_guidance ---

class TestGuidanceNote:
    def test_circuit_excludes_rest_guidance(self):
        block = _make_circuit_block(
            [{"name": "KB Swings", "reps": 10}],
            rest_guidance="90 sec rest after each round",
            rounds=4,
        )
        results = _transform_block_to_exercises(block, 0)
        assert results[0].get("guidance_note") is None

    def test_power_excludes_rest_guidance(self):
        block = _make_circuit_block(
            [{"name": "Box Jump", "reps": 5, "notes": "Explosive"}],
            rest_guidance="60 sec rest after each round",
            rounds=5,
            block_type="power",
        )
        results = _transform_block_to_exercises(block, 0)
        assert "60 sec rest" not in results[0]["guidance_note"]
        assert "Explosive" in results[0]["guidance_note"]

    def test_circuit_exercise_notes_still_shown(self):
        block = _make_circuit_block(
            [{"name": "KB Swings", "reps": 10, "load_guide": "Heavy"}],
            rounds=4,
        )
        results = _transform_block_to_exercises(block, 0)
        assert results[0]["guidance_note"] == "Heavy"

    def test_strength_includes_rest_guidance(self):
        block = {
            "block_type": "strength",
            "title": "Strength",
            "rest_guidance": "Rest 2-3 min",
            "exercises": [{"name": "Squat", "reps": 5}],
        }
        results = _transform_block_to_exercises(block, 0)
        assert "Rest 2-3 min" in results[0]["guidance_note"]


# --- show_time for duration-based reps ---

class TestShowTime:
    @pytest.mark.parametrize("reps", [
        "30 sec",
        "30 sec/side",
        "45 seconds",
        "20 SEC",
    ])
    def test_duration_reps_set_show_time(self, reps):
        block = _make_circuit_block([{"name": "Wall Sit", "reps": reps}])
        results = _transform_block_to_exercises(block, 0)
        assert results[0].get("show_time") is True
        assert results[0]["target_reps"] == reps

    @pytest.mark.parametrize("reps", [
        10,
        "10",
        "8/leg",
        "10/side",
    ])
    def test_non_duration_reps_no_show_time(self, reps):
        block = _make_circuit_block([{"name": "KB Swings", "reps": reps}])
        results = _transform_block_to_exercises(block, 0)
        assert "show_time" not in results[0]

    def test_no_reps_no_show_time(self):
        block = _make_circuit_block([{"name": "KB Swings"}])
        results = _transform_block_to_exercises(block, 0)
        assert "show_time" not in results[0]


# --- _is_bodyweight_or_band ---

class TestIsBodyweightOrBand:
    def test_pushup_variants(self):
        assert _is_bodyweight_or_band("Push-ups") is True
        assert _is_bodyweight_or_band("Pushup") is True
        assert _is_bodyweight_or_band("Wide Push Up") is True

    def test_band_exercises(self):
        assert _is_bodyweight_or_band("Band Pull-Aparts") is True
        assert _is_bodyweight_or_band("Banded Face Pulls") is True

    def test_weighted_exercises(self):
        assert _is_bodyweight_or_band("KB Swings") is False
        assert _is_bodyweight_or_band("Barbell Squat") is False
