from __future__ import annotations

import json

from auto_vlm.vlm.evaluation_scope import build_evaluation_scope


def test_od_evaluation_scope_annotates_vehicle_and_vru_ranges(tmp_path):
    json_path = tmp_path / "frame_00000100.json"
    json_path.write_text(
        json.dumps(
            {
                "avi_objects": {
                    "VIS_OBJ_Element": [
                        {
                            "VIS_OBJ_ID": 1,
                            "VIS_OBJ_Object_Class": "car",
                            "VIS_OBJ_Physical_State": {"Long_Distance": 82.0},
                        },
                        {
                            "VIS_OBJ_ID": 2,
                            "VIS_OBJ_Object_Class": "car",
                            "VIS_OBJ_Physical_State": {"Long_Distance": 142.0},
                        },
                        {
                            "VIS_OBJ_ID": 3,
                            "VIS_OBJ_Object_Class": "pedestrian",
                            "VIS_OBJ_Physical_State": {"Long_Distance": 65.0},
                        },
                        {
                            "VIS_OBJ_ID": 4,
                            "VIS_OBJ_Object_Class": "motorcycle",
                            "VIS_OBJ_Physical_State": {"Long_Distance": 91.0},
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    scope = build_evaluation_scope(json_path)
    od = scope["features"]["OD"]
    by_id = {item["object_id"]: item for item in od["objects"]}

    assert od["rules"] == {
        "vehicle_max_long_distance_m": 100.0,
        "vru_max_long_distance_m": 70.0,
    }
    assert by_id["1"]["scope"] == "in_scope"
    assert by_id["2"]["scope"] == "out_of_scope"
    assert by_id["3"]["scope"] == "in_scope"
    assert by_id["4"]["scope"] == "out_of_scope"
    assert od["summary"] == {"in_scope": 2, "out_of_scope": 2, "scope_uncertain": 0}


def test_od_evaluation_scope_keeps_unknown_class_or_distance_uncertain(tmp_path):
    json_path = tmp_path / "frame_00000100.json"
    json_path.write_text(
        json.dumps(
            {
                "objects": [
                    {"id": "A", "class": "unknown", "long_distance": 40.0},
                    {"id": "B", "class": "car"},
                ]
            }
        ),
        encoding="utf-8",
    )

    scope = build_evaluation_scope(json_path)
    by_id = {item["object_id"]: item for item in scope["features"]["OD"]["objects"]}

    assert by_id["A"]["scope"] == "scope_uncertain"
    assert by_id["A"]["reason"] == "class unknown; do not exclude by scope"
    assert by_id["B"]["scope"] == "scope_uncertain"
    assert by_id["B"]["reason"] == "long_distance unavailable; do not exclude by scope"
