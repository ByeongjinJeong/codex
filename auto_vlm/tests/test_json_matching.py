from __future__ import annotations

import json

from auto_vlm.conversion.json_matcher import match_frame_json
from auto_vlm.models.evidence import JsonFrameMatchStatus, JsonParseStatus


def test_exact_frame_json_match_copies_snippet_and_summarizes(tmp_path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    (json_dir / "00000100.json").write_text(
        json.dumps(
            {
                "frame_id": 100,
                "objects": [{"id": 1, "class": "vehicle"}, {"id": 2, "class": "pedestrian"}],
                "lanes": [{"track_id": 10}, {"track_id": 11}],
                "traffic_signs": [],
            }
        ),
        encoding="utf-8",
    )

    result = match_frame_json(json_dir, 100, tmp_path / "output/json_snippets", focus_feature="OD")

    assert result.json_snippet is not None
    assert result.json_snippet.exists()
    assert result.evidence_integrity.json_frame_match_status == JsonFrameMatchStatus.EXACT
    assert result.evidence_integrity.json_parse_status == JsonParseStatus.OK
    assert "objects=2" in result.json_summary
    assert "lanes=2" in result.json_summary
    assert "OD_classes=vehicle,pedestrian" in result.json_summary


def test_missing_json_dir_records_integrity_not_failure(tmp_path):
    result = match_frame_json(tmp_path / "missing", 100, tmp_path / "output/json_snippets")

    assert result.json_snippet is None
    assert result.evidence_integrity.json_available is False
    assert result.evidence_integrity.json_frame_match_status == JsonFrameMatchStatus.MISSING_JSON_DIR
    assert result.evidence_integrity.json_parse_status == JsonParseStatus.MISSING


def test_missing_frame_json_records_missing_frame(tmp_path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()

    result = match_frame_json(json_dir, 100, tmp_path / "output/json_snippets")

    assert result.json_snippet is None
    assert result.evidence_integrity.json_available is True
    assert result.evidence_integrity.json_frame_match_status == JsonFrameMatchStatus.MISSING_FRAME_JSON
    assert result.json_summary == "frame json missing"


def test_malformed_json_records_parse_error_and_keeps_snippet(tmp_path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    (json_dir / "00000100.json").write_text("{bad json", encoding="utf-8")

    result = match_frame_json(json_dir, 100, tmp_path / "output/json_snippets")

    assert result.json_snippet is not None
    assert result.json_snippet.exists()
    assert result.evidence_integrity.json_parse_status == JsonParseStatus.MALFORMED
    assert result.json_summary == "frame json malformed"


def test_frame_id_mismatch_sets_offset_suspicion(tmp_path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    (json_dir / "00000100.json").write_text(json.dumps({"frame_id": 101}), encoding="utf-8")

    result = match_frame_json(json_dir, 100, tmp_path / "output/json_snippets")

    assert result.evidence_integrity.json_offset_suspected is True
    assert "differs" in result.evidence_integrity.integrity_notes[0]
