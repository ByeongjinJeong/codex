"""QV overlay region extraction shared by feature and candidate evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2

from auto_vlm.models.evidence import FrameEvidencePackage


def write_full_ics_region(
    package: FrameEvidencePackage,
    image_path: Path | None,
    output_path: Path,
) -> tuple[Path | None, str]:
    """Write the full ICS/raw-layout side of a QV overlay frame."""
    image, status = _load_overlay_image(package, image_path)
    if image is None:
        return None, status
    height, width = image.shape[:2]
    raw_width = package.raw_video_metadata.width
    if width < raw_width:
        return None, "unavailable_layout_mismatch"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image[0:height, 0:raw_width])
    return output_path, "available_raw_layout"


def write_full_bev_region(
    package: FrameEvidencePackage,
    image_path: Path | None,
    output_path: Path,
) -> tuple[Path | None, str]:
    """Write the full BEV/world-space side of a QV overlay frame."""
    image, status = _load_overlay_image(package, image_path)
    if image is None:
        return None, status
    height, width = image.shape[:2]
    raw_width = package.raw_video_metadata.width
    if width <= raw_width:
        return None, "unavailable_no_bev_region"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image[0:height, raw_width:width])
    return output_path, "available_overlay_right_of_raw"


def write_object_ics_region(
    package: FrameEvidencePackage,
    image_path: Path | None,
    objects: list[dict[str, Any]],
    output_path: Path,
) -> tuple[Path | None, str]:
    """Write a focused ICS/raw-layout crop around candidate object image boxes."""
    image, status = _load_overlay_image(package, image_path)
    if image is None:
        return None, status

    union = _union_image_box(objects)
    if union is None:
        return None, "unavailable_or_unverified"

    height, width = image.shape[:2]
    raw_width = package.raw_video_metadata.width
    if width < raw_width:
        return None, "unavailable_layout_mismatch"
    x0, y0, x1, y1 = _clamped_padded_box(union, raw_width, height)
    if x1 <= x0 or y1 <= y0:
        return None, "unavailable_or_unverified"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image[y0:y1, x0:x1])
    return output_path, "available_raw_layout"


def _load_overlay_image(
    package: FrameEvidencePackage,
    image_path: Path | None,
) -> tuple[Any | None, str]:
    if image_path is None or not image_path.exists():
        return None, "unavailable_or_unverified"
    if package.raw_video_metadata is None or package.raw_video_metadata.width <= 0:
        return None, "unavailable_raw_layout"
    image = cv2.imread(str(image_path))
    if image is None:
        return None, "unavailable_or_unverified"
    if image.shape[0] <= 0:
        return None, "unavailable_layout_mismatch"
    return image, "available"


def _union_image_box(objects: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    boxes = []
    for obj in objects:
        coords = obj.get("VIS_OBJ_Image_Coordinates")
        if not isinstance(coords, dict):
            continue
        xs = [value for key, value in coords.items() if key.endswith("_X") and isinstance(value, (int, float))]
        ys = [value for key, value in coords.items() if key.endswith("_Y") and isinstance(value, (int, float))]
        if xs and ys:
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _clamped_padded_box(
    box: tuple[float, float, float, float],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    pad = max(12, int(max(x1 - x0, y1 - y0) * 0.2))
    return (
        max(0, int(x0) - pad),
        max(0, int(y0) - pad),
        min(width, int(x1) + pad),
        min(height, int(y1) + pad),
    )
