from __future__ import annotations

from auto_vlm.conversion.json_matcher import summarize_frame_json


def test_minimum_summary_counts_common_feature_groups():
    summary = summarize_frame_json(
        {
            "frame_id": 42,
            "processed": {
                "objects": [{"id": 1}, {"id": 2}, {"id": 3}],
                "lanes": [{"id": 10}],
                "road_edges": [{"id": 20}, {"id": 21}],
                "traffic_lights": [{"id": 30}],
                "road_markings": [],
            },
            "failsafe_status": "degraded",
        }
    )

    assert "frame_id=42" in summary
    assert "objects=3" in summary
    assert "lanes=1" in summary
    assert "road_edges=2" in summary
    assert "lights=1" in summary
    assert "failsafe_status=degraded" in summary


def test_feature_specific_ld_summary_includes_ids():
    summary = summarize_frame_json(
        {
            "lanes": [
                {"track_id": "L1", "role": "ego_left"},
                {"track_id": "L2", "role": "ego_right"},
            ]
        },
        focus_feature="LD",
    )

    assert "LD_ids=L1,L2" in summary


def test_feature_specific_summary_accepts_multiple_features():
    summary = summarize_frame_json(
        {
            "objects": [{"id": 1, "class": "vehicle"}],
            "lanes": [{"track_id": "L1"}],
            "road_edges": [{"track_id": "R1"}],
        },
        focus_feature="OD,RBD",
    )

    assert "OD_classes=vehicle" in summary
    assert "RBD_ids=" in summary
    assert "L1" in summary
    assert "R1" in summary


def test_feature_specific_traffic_light_summary_includes_states():
    summary = summarize_frame_json(
        {
            "traffic_lights": [
                {"id": 1, "struct_state": "red"},
                {"id": 2, "struct_state": "green"},
            ]
        },
        focus_feature="TL",
    )

    assert "TL_states=red,green" in summary


def test_qv_native_sections_are_counted_without_dumping_nested_status_dicts():
    summary = summarize_frame_json(
        {
            "avi_objects": {"VIS_OBJ_Element": [{"id": 1}, {"id": 2}]},
            "avi_lanes_host": {"VIS_LH_Element": [{"id": "L1"}]},
            "avi_lanes_road_edge": {"VIS_LRE_Element": [{"id": "R1"}]},
            "avi_calibration": {
                "VIS_Calibration_Header": {
                    "Current_Status": 4294967295,
                    "Current_Error_Reason": {"Internal": 0},
                }
            },
        }
    )

    assert "objects=2" in summary
    assert "lanes=1" in summary
    assert "road_edges=1" in summary
    assert "Current_Status=4294967295" in summary
    assert "Current_Error_Reason={'Internal': 0}" not in summary


def test_qv_native_od_summary_includes_heading_and_overlap_hints():
    summary = summarize_frame_json(
        {
            "avi_objects": {
                "VIS_OBJ_Element": [
                    {
                        "VIS_OBJ_ID": 171,
                        "VIS_OBJ_Object_Class": 2,
                        "VIS_OBJ_Physical_State": {"Heading": -3.13},
                        "VIS_OBJ_Motion_State": {"Motion_Orientation": 6},
                        "VIS_OBJ_Image_Coordinates": {
                            "Rect_Back_Bottom_Left_X": 100,
                            "Rect_Back_Bottom_Left_Y": 100,
                            "Rect_Front_Top_Right_X": 300,
                            "Rect_Front_Top_Right_Y": 300,
                        },
                    },
                    {
                        "VIS_OBJ_ID": 183,
                        "VIS_OBJ_Object_Class": 1,
                        "VIS_OBJ_Physical_State": {"Heading": -3.08},
                        "VIS_OBJ_Motion_State": {"Motion_Orientation": 6},
                        "VIS_OBJ_Image_Coordinates": {
                            "Rect_Back_Bottom_Left_X": 220,
                            "Rect_Back_Bottom_Left_Y": 150,
                            "Rect_Front_Top_Right_X": 320,
                            "Rect_Front_Top_Right_Y": 260,
                        },
                    },
                ]
            }
        }
    )

    assert "OD_heading_samples=171:-3.13/o6,183:-3.08/o6" in summary
    assert "OD_bbox_overlap_candidates=171-183:" in summary


def test_qv_native_od_summary_includes_large_bbox_hint():
    summary = summarize_frame_json(
        {
            "avi_objects": {
                "VIS_OBJ_Element": [
                    {
                        "VIS_OBJ_ID": 60,
                        "VIS_OBJ_Physical_State": {"Heading": -0.65},
                        "VIS_OBJ_Motion_State": {"Motion_Orientation": 11},
                        "VIS_OBJ_Image_Coordinates": {
                            "Rect_Back_Bottom_Left_X": 700,
                            "Rect_Back_Bottom_Left_Y": 900,
                            "Rect_Back_Bottom_Right_X": 1900,
                            "Rect_Back_Bottom_Right_Y": 1900,
                            "Rect_Back_Top_Left_X": 700,
                            "Rect_Back_Top_Left_Y": 900,
                            "Rect_Back_Top_Right_X": 1900,
                            "Rect_Back_Top_Right_Y": 900,
                        },
                    },
                    {
                        "VIS_OBJ_ID": 21,
                        "VIS_OBJ_Physical_State": {"Heading": 0.01},
                        "VIS_OBJ_Motion_State": {"Motion_Orientation": 12},
                        "VIS_OBJ_Image_Coordinates": {
                            "Rect_Back_Bottom_Left_X": 1900,
                            "Rect_Back_Bottom_Left_Y": 1100,
                            "Rect_Back_Bottom_Right_X": 2000,
                            "Rect_Back_Bottom_Right_Y": 1200,
                            "Rect_Back_Top_Left_X": 1900,
                            "Rect_Back_Top_Left_Y": 1100,
                            "Rect_Back_Top_Right_X": 2000,
                            "Rect_Back_Top_Right_Y": 1100,
                        },
                    },
                ]
            }
        }
    )

    assert "OD_large_bbox_candidates=60:" in summary


def test_qv_native_summary_flags_low_road_edge_count_for_rbd_review():
    summary = summarize_frame_json(
        {
            "avi_lanes_host": {"VIS_LH_Element": [{"id": "L1"}, {"id": "L2"}]},
            "avi_lanes_road_edge": {"VIS_LRE_Element": [{"id": "R1"}]},
        }
    )

    assert "lanes=2" in summary
    assert "road_edges=1" in summary
    assert "RBD_low_road_edge_count=1/expected_min=2" in summary
