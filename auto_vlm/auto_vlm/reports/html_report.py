"""Focused static summary.html writer."""

from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

from auto_vlm.models.evidence import FrameEvidencePackage
from auto_vlm.models.results import FeatureReviewResult, FrameTestResult, PackageReviewResult
from auto_vlm.reports.korean_text import feature_inference, feature_summary
from auto_vlm.utils.errors import ToolError


def write_summary_html(
    output_path: str | Path,
    packages: list[FrameEvidencePackage],
    results: dict[str, PackageReviewResult] | None = None,
    errors: list[ToolError] | None = None,
    review_quality_status: str = "not_run",
) -> Path:
    results = results or {}
    errors = errors or []
    output = Path(output_path)
    output_dir = output.parent
    package_results = [(package, results.get(package.package_id, PackageReviewResult())) for package in packages]
    counts = _count_results(package_results, errors)

    body = [
        "<!doctype html>",
        "<html lang='ko'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Auto VLM 기능 검토 리포트</title>",
        f"<style>{_stylesheet()}</style>",
        "</head><body>",
        "<main class='shell'>",
        _render_header(counts, review_quality_status),
        *[
            _render_package(index, package, result, output_dir)
            for index, (package, result) in enumerate(package_results, start=1)
        ],
        *[_render_error(index, error) for index, error in enumerate(errors, start=1)],
        "</main>",
        "</body></html>",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(body), encoding="utf-8")
    return output


def _count_results(
    package_results: list[tuple[FrameEvidencePackage, PackageReviewResult]],
    errors: list[ToolError],
) -> dict[str, int]:
    frame_counts = Counter(result.frame_result.value for _, result in package_results)
    feature_counts = Counter(
        feature.result.value
        for _, result in package_results
        for feature in result.feature_results
    )
    return {
        "frames": len(package_results),
        "frame_pass": frame_counts["pass"],
        "frame_fail": frame_counts["fail"],
        "frame_needs_review": frame_counts["needs_review"],
        "feature_pass": feature_counts["pass"],
        "feature_fail": feature_counts["fail"],
        "feature_needs_review": feature_counts["needs_review"],
        "tool_error": len(errors),
    }


def _render_header(counts: dict[str, int], review_quality_status: str) -> str:
    return "\n".join(
        [
            "<header class='report-header'>",
            "<div>",
            "<p class='eyebrow'>Auto VLM</p>",
            "<h1>기능 검토 리포트</h1>",
            f"<p class='review-state'>검토 품질: {escape(review_quality_status)}</p>",
            "</div>",
            "<div class='summary'>",
            _metric("프레임", counts["frames"]),
            _metric("프레임 FAIL", counts["frame_fail"]),
            _metric("기능 FAIL", counts["feature_fail"]),
            _metric("도구 오류", counts["tool_error"]),
            "</div>",
            "</header>",
        ]
    )


def _metric(label: str, value: int) -> str:
    return f"<div class='metric'><span>{escape(label)}</span><strong>{value}</strong></div>"


def _render_package(
    index: int,
    package: FrameEvidencePackage,
    result: PackageReviewResult,
    output_dir: Path,
) -> str:
    qv_frame = package.qv_overlay_frame_image or package.center_frame_image
    feature_rows = _render_feature_rows(package, result.feature_results, output_dir)
    if not feature_rows:
        feature_rows = (
            "<tr><td colspan='3' class='empty'>기능별 검토 결과가 로드되지 않았습니다.</td></tr>"
        )
    search_text = " ".join(
        [
            package.case_id,
            str(package.sampled_frame),
            result.frame_result.value,
            " ".join(feature.feature for feature in result.feature_results),
            " ".join(_feature_basis_text(package, feature) for feature in result.feature_results),
        ]
    )
    return "\n".join(
        [
            f"<article id='pkg-{index}' class='frame-card {_risk_class(result.frame_result)}' data-search='{escape(search_text.lower())}'>",
            "<section class='overlay-panel'>",
            "<div class='frame-title'>",
            f"<h2>{escape(package.case_id)} · Frame {package.sampled_frame}</h2>",
            f"<span class='review-mode'>{escape(package.review_mode)}</span>",
            f"<span class='frame-result {escape(result.frame_result.value)}'>{escape(_result_label(result.frame_result))}</span>",
            "</div>",
            _figure(qv_frame, "QV 오버레이", output_dir),
            _render_evidence_links(package, output_dir),
            "</section>",
            "<section class='feature-panel'>",
            "<table>",
            "<thead><tr><th>기능</th><th>결과</th><th>판단 근거</th></tr></thead>",
            f"<tbody>{feature_rows}</tbody>",
            "</table>",
            "</section>",
            "</article>",
        ]
    )


def _render_feature_rows(
    package: FrameEvidencePackage,
    features: tuple[FeatureReviewResult, ...],
    output_dir: Path,
) -> str:
    rows = []
    for feature in features:
        rows.append(
            "\n".join(
                [
                    f"<tr class='{escape(feature.result.value)}'>",
                    f"<td class='feature-name'>{escape(feature.feature)}</td>",
                    f"<td><span class='pill {escape(feature.result.value)}'>{escape(_result_label(feature.result))}</span></td>",
                    f"<td>{_render_feature_basis(package, feature, output_dir)}</td>",
                    "</tr>",
                ]
            )
        )
    return "\n".join(rows)


def _render_feature_basis(
    package: FrameEvidencePackage,
    feature: FeatureReviewResult,
    output_dir: Path,
) -> str:
    blocks = [
        ("검출 이슈", ", ".join(feature.triggered_issue_types)),
        ("평가 이슈", ", ".join(feature.evaluated_issue_types)),
        ("Crop 산출물", _feature_crop_links(package, feature, output_dir)),
        ("판단 근거", feature_inference(package, feature)),
    ]
    if feature.result != FrameTestResult.PASS:
        blocks.insert(2, ("이슈 요약", feature_summary(package, feature)))
    rendered = [
        _basis_block(title, value)
        for title, value in blocks
        if value and value.strip()
    ]
    if not rendered:
        rendered.append(_basis_block("판단 근거", "LLM 판단 근거가 결과 파일에 포함되지 않았습니다."))
    return "<div class='basis'>" + "\n".join(rendered) + "</div>"


def _feature_crop_links(
    package: FrameEvidencePackage,
    feature: FeatureReviewResult,
    output_dir: Path | None = None,
) -> str:
    packets = [
        packet
        for packet in package.feature_evidence_packets
        if packet.feature == feature.feature
    ]
    if not packets:
        return ""
    packet = packets[0]
    links = [
        ("기능 ICS crop", packet.ics_crop_image),
        ("기능 BEV crop", packet.bev_crop_image),
        ("기능 패킷", packet.packet_markdown),
    ]
    return _artifact_links(links, output_dir)


def _feature_basis_text(package: FrameEvidencePackage, feature: FeatureReviewResult) -> str:
    return " ".join(
        value.strip()
        for value in (
            feature_summary(package, feature),
            feature_inference(package, feature),
        )
        if value and value.strip()
    )


def _basis_block(title: str, value: str) -> str:
    return "\n".join(
        [
            "<section class='basis-block'>",
            f"<h3>[{escape(title)}]</h3>",
            f"<p>{value if 'artifact-links' in value else escape(value)}</p>",
            "</section>",
        ]
    )


def _artifact_links(links: list[tuple[str, Path | None]], output_dir: Path | None) -> str:
    rendered = []
    for label, path in links:
        if path is None:
            continue
        href = _href(path, output_dir) if output_dir is not None else escape(str(path))
        rendered.append(
            f"<a href='{href}' target='_blank' rel='noopener'>{escape(label)}</a>"
        )
    if not rendered:
        return ""
    return "<span class='artifact-links'>" + "\n".join(rendered) + "</span>"


def _figure(path: Path | None, label: str, output_dir: Path) -> str:
    if path is None:
        return f"<figure><div class='missing'>오버레이 이미지 없음</div><figcaption>{escape(label)}</figcaption></figure>"
    return "\n".join(
        [
            "<figure>",
            f"<img src='{_href(path, output_dir)}' alt='{escape(label)}'>",
            f"<figcaption>{escape(label)}</figcaption>",
            "</figure>",
        ]
    )


def _render_evidence_links(package: FrameEvidencePackage, output_dir: Path) -> str:
    links = [
        ("원본 프레임", package.raw_frame_image),
        ("QV 프레임", package.qv_overlay_frame_image or package.center_frame_image),
        ("JSON", package.json_snippet),
    ]
    rendered = [
        f"<a href='{_href(path, output_dir)}' target='_blank' rel='noopener'>{escape(label)}</a>"
        for label, path in links
        if path is not None
    ]
    if not rendered:
        return ""
    return "<nav class='evidence-links'>" + "\n".join(rendered) + "</nav>"


def _render_error(index: int, error: ToolError) -> str:
    return "\n".join(
        [
            f"<article id='tool-error-{index}' class='frame-card fail'>",
            "<section class='feature-panel wide'>",
            f"<h2>{escape(error.case_id or 'Tool Error')}</h2>",
            "<table>",
            "<thead><tr><th>기능</th><th>결과</th><th>판단 근거</th></tr></thead>",
            "<tbody>",
            "<tr class='fail'>",
            "<td class='feature-name'>TOOL</td>",
            "<td><span class='pill fail'>FAIL</span></td>",
            f"<td>{escape(error.as_message())}</td>",
            "</tr>",
            "</tbody>",
            "</table>",
            "</section>",
            "</article>",
        ]
    )


def _href(path: Path, output_dir: Path) -> str:
    try:
        href = Path(path).resolve().relative_to(output_dir.resolve())
    except ValueError:
        href = Path(path).resolve()
    return escape(href.as_posix())


def _risk_class(result: FrameTestResult) -> str:
    return {
        FrameTestResult.FAIL: "fail",
        FrameTestResult.NEEDS_REVIEW: "needs_review",
        FrameTestResult.PASS: "pass",
    }[result]


def _result_label(result: FrameTestResult) -> str:
    return {
        FrameTestResult.PASS: "PASS",
        FrameTestResult.FAIL: "FAIL",
        FrameTestResult.NEEDS_REVIEW: "NEEDS REVIEW",
    }[result]


def _stylesheet() -> str:
    return """
:root {
  --bg: #f6f7f9;
  --panel: #ffffff;
  --text: #171b26;
  --muted: #647084;
  --border: #d9dee7;
  --pass: #087443;
  --fail: #b42318;
  --review: #b54708;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Aptos", "Segoe UI", sans-serif;
}
.shell {
  max-width: 1500px;
  margin: 0 auto;
  padding: 24px;
}
.report-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: end;
  margin-bottom: 18px;
}
.eyebrow {
  margin: 0 0 6px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.review-state {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}
h1, h2 { margin: 0; }
h1 { font-size: 30px; }
h2 { font-size: 20px; }
.summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(110px, 1fr));
  gap: 8px;
  min-width: 520px;
}
.metric {
  padding: 10px 12px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.metric span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}
.metric strong {
  display: block;
  margin-top: 3px;
  font-size: 22px;
}
.frame-card {
  display: grid;
  grid-template-columns: minmax(520px, 0.95fr) minmax(520px, 1.05fr);
  gap: 16px;
  align-items: start;
  margin-bottom: 16px;
  padding: 16px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-left: 5px solid var(--muted);
  border-radius: 8px;
  min-width: 0;
}
.frame-card.pass { border-left-color: var(--pass); }
.frame-card.fail { border-left-color: var(--fail); }
.frame-card.needs_review { border-left-color: var(--review); }
.overlay-panel,
.feature-panel {
  min-width: 0;
}
.frame-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}
.review-mode {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
}
.frame-result, .pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 86px;
  padding: 5px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}
.pass { color: var(--pass); }
.fail { color: var(--fail); }
.needs_review { color: var(--review); }
.pill.pass, .frame-result.pass { background: #ecfdf3; border: 1px solid #abefc6; }
.pill.fail, .frame-result.fail { background: #fef3f2; border: 1px solid #fecdca; }
.pill.needs_review, .frame-result.needs_review { background: #fff7ed; border: 1px solid #fed7aa; }
figure {
  margin: 0;
  background: #101828;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
img {
  display: block;
  width: 100%;
  max-height: 620px;
  object-fit: contain;
  background: #101828;
}
figcaption {
  padding: 8px 10px;
  color: #e4e7ec;
  font-size: 12px;
  background: #111827;
}
.evidence-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.evidence-links a {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 5px 9px;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  background: #f8fafc;
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}
.evidence-links a:hover {
  border-color: var(--muted);
  background: #eef2f7;
}
.artifact-links {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.artifact-links a {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  background: #ffffff;
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
}
.artifact-links a:hover {
  border-color: var(--muted);
  background: #eef2f7;
}
.missing {
  display: grid;
  min-height: 240px;
  place-items: center;
  color: #e4e7ec;
}
table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  min-width: 0;
}
th, td {
  padding: 10px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: break-word;
}
td { max-width: 0; }
th {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  background: #f2f4f7;
}
th:nth-child(1), td:nth-child(1) { width: 90px; }
th:nth-child(2), td:nth-child(2) { width: 130px; }
.feature-name {
  font-weight: 800;
}
.basis {
  display: grid;
  gap: 10px;
}
.basis-block {
  padding: 9px 10px;
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 6px;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.basis-block h3 {
  margin: 0 0 5px;
  color: var(--muted);
  font-size: 12px;
}
.basis-block p {
  margin: 0;
  white-space: pre-wrap;
  max-height: 220px;
  overflow: auto;
}
.empty {
  color: var(--muted);
}
.wide {
  grid-column: 1 / -1;
}
@media (max-width: 1100px) {
  .report-header,
  .frame-card {
    display: block;
  }
  .summary {
    min-width: 0;
    margin-top: 12px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .feature-panel {
    margin-top: 14px;
  }
}
"""
