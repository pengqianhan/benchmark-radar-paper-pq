#!/usr/bin/env python3
"""Record figure release dates that the latest software catalog does not carry.

Compares every frozen source record in the Figure 6 date input with a cleanly
rebuilt Benchmark Radar software checkout. The software catalog is the
reference for dates it provides; records dated only by this paper's reviewed
supplements are listed with their date, evidence and derivation.
"""

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
ROWS = PAPER / "evidence/benchmark-taxonomy-dated.jsonl"
CENSUS = PAPER / "evidence/catalog-findings.json"
MATCHES = PAPER / "evidence/release-date-matches.json"
SUPPLEMENTS = PAPER / "evidence/taxonomy-release-date-supplements.json"
OUT_JSON = PAPER / "evidence/software-release-date-gaps.json"
OUT_CSV = PAPER / "evidence/software-release-date-gaps.csv"
OUT_MD = PAPER / "evidence/software-release-date-gaps.md"
INDEX = "site/data/benchmark-index.json"
SOFTWARE_DATE_INPUTS = ["data/catalog/benchmark_dates.yml", "data/model_cards.yml"]
WINDOW_START_YEAR = 2023

CSV_FIELDS = [
    "catalogKey", "name", "source", "l1", "release_date", "precision", "figure_period",
    "event", "date_scope", "evidence_source", "input_file", "date_field", "match_method",
    "libraryId", "evidence_basis", "evidence_note", "reviewed_at", "source_urls", "reason",
    "software_released", "software_first_score_reported_at",
]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(software, *args):
    return subprocess.run(["git", "-C", str(software), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def figure_period(value):
    """Panel A half-year period for a date; earlier records stay in the data but are not drawn."""
    if not value:
        return "undated"
    year = int(value[:4])
    if year < WINDOW_START_YEAR:
        return f"before {WINDOW_START_YEAR} (not drawn)"
    return f"{year} H{1 if int(value[5:7]) <= 6 else 2}"


def evidence_detail(match):
    """The reviewed date evidence the paper adopted for one record."""
    if match["evidence_source"] == "library":
        ev = match.get("releaseEvidence") or {}
        return {"basis": ev.get("basis"), "note": ev.get("note"), "reviewed_at": ev.get("reviewedAt"),
                "source_url": ev.get("sourceUrl")}
    ev = match.get("nextVerification") or {}
    return {"basis": ev.get("basis"), "note": ev.get("reason"), "reviewed_at": ev.get("checkedAt"),
            "source_url": None}


def build(software):
    software = Path(software).resolve()
    rows = [json.loads(line) for line in ROWS.read_text().splitlines()]
    census = {r["key"]: r for r in json.loads(CENSUS.read_text())["records"]}
    matches = {r["catalogKey"]: r for r in json.loads(MATCHES.read_text())["records"]}
    supplements = {r["catalogKey"]: r for r in json.loads(SUPPLEMENTS.read_text())["records"]}
    latest = {b["key"]: b for b in json.loads((software / INDEX).read_text())["benchmarks"]}
    if [r["key"] for r in rows] != list(census):
        raise ValueError("Figure date input must retain the exact frozen census order")

    comparison, gaps = Counter(), []
    for row in rows:
        key, figure_date = row["key"], row.get("release_date")
        if key not in latest:
            raise ValueError(f"Frozen record missing from software catalog: {key}")
        software_date = latest[key].get("released")
        if figure_date == software_date:
            comparison["same_date" if figure_date else "both_undated"] += 1
        elif figure_date and not software_date:
            comparison["figure_dated_software_undated"] += 1
            gaps.append(row)
        elif software_date and not figure_date:
            comparison["software_dated_figure_undated"] += 1
        else:
            comparison["different_date"] += 1
    if comparison["different_date"] or comparison["software_dated_figure_undated"]:
        raise ValueError(f"Software dates conflict with the figure input: {dict(comparison)}")

    records = []
    for row in gaps:
        key = row["key"]
        match, software_record = matches[key], latest[key]
        if census[key].get("release_date") is not None or match["decision"] != "accepted":
            raise ValueError(f"Undated software record lacks an accepted paper supplement: {key}")
        if supplements[key]["release_date"] != row["release_date"] or match["release_date"] != row["release_date"]:
            raise ValueError(f"Supplement and figure dates disagree: {key}")
        detail = evidence_detail(match)
        records.append({
            "catalogKey": key,
            "name": row["name"],
            "source": row["source"],
            "l1": row["l1"],
            "release_date": row["release_date"],
            "precision": match["precision"],
            "figure_period": figure_period(row["release_date"]),
            "event": match["event"],
            "date_scope": match.get("date_scope"),
            "evidence_source": match["evidence_source"],
            "input_file": match["input_file"],
            "date_field": match["date_field"],
            "match_method": match["match_method"],
            "libraryId": match.get("libraryId"),
            "evidence": detail,
            "source_urls": [s["url"] for s in match.get("sources") or [] if s.get("url")],
            "reason": match["reason"],
            "software": {
                "released": software_record.get("released"),
                "released_reference": software_record.get("released_reference"),
                "first_score_reported_at": software_record.get("first_score_reported_at"),
            },
        })

    report = {
        "schema_version": 1,
        "definition": (
            "Frozen Figure 6 source records whose release/introduction date comes only from this "
            "paper's reviewed supplements because the latest software catalog has no release date. "
            "Where both carry a date they agree, so the software catalog remains the reference for "
            "every date it provides. first_score_reported_at is a model-score date, not a release date."
        ),
        "derivation": {
            "library": "match_library_dates.py: releaseEvidence.date from evidence/library-reviewed-dates.json, "
                       "matched by exact catalog/sourceId or reviewed identity in "
                       "evidence/library-date-match-reviews.json; only official introduction/release events.",
            "legacy_next_verification": "supplement_taxonomy_dates.py: passed nextVerification.releaseDate from "
                                        "evidence/156_from_xiaoke_all_passed_en.json for the exact keys in "
                                        "evidence/release-date-legacy-selection.json.",
            "software": "Software release dates come from source crawls, data/catalog/benchmark_dates.yml and "
                        "data/model_cards.yml; none of them dates these records.",
        },
        "software": {
            "commit": git(software, "rev-parse", "HEAD"),
            "commit_date": git(software, "log", "-1", "--format=%cI"),
            # The build itself rewrites tracked site/ outputs; the date inputs must match the commit.
            "tracked_input_changes": bool(git(software, "status", "--porcelain", "--untracked-files=no",
                                              "--", "data", "src")),
            "build": ["benchmark-radar normalize-catalog", "benchmark-radar classify",
                      "benchmark-radar build-data-release"],
            "index_records": len(latest),
            "input_sha256": {p: sha256(software / p) for p in SOFTWARE_DATE_INPUTS},
        },
        "paper_input_sha256": {str(p.relative_to(PAPER)): sha256(p)
                               for p in (ROWS, CENSUS, MATCHES, SUPPLEMENTS)},
        "population": len(rows),
        "comparison": {k: comparison[k] for k in ("same_date", "both_undated", "figure_dated_software_undated",
                                                  "different_date", "software_dated_figure_undated")},
        "counts": {
            "evidence_source": dict(sorted(Counter(r["evidence_source"] for r in records).items())),
            "source": dict(sorted(Counter(r["source"] for r in records).items())),
            "precision": dict(sorted(Counter(r["precision"] for r in records).items())),
            "figure_period": dict(sorted(Counter(r["figure_period"] for r in records).items())),
            "with_first_score_date": sum(1 for r in records if r["software"]["first_score_reported_at"]),
        },
        "records": records,
    }
    return report


def to_csv(report):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for r in report["records"]:
        writer.writerow({**{k: r.get(k) or "" for k in CSV_FIELDS},
                         "evidence_basis": r["evidence"]["basis"] or "",
                         "evidence_note": r["evidence"]["note"] or "",
                         "reviewed_at": r["evidence"]["reviewed_at"] or "",
                         "source_urls": " ".join(r["source_urls"]),
                         "software_released": r["software"]["released"] or "",
                         "software_first_score_reported_at": r["software"]["first_score_reported_at"] or ""})
    return out.getvalue()


def to_markdown(report):
    sw, cmp, counts = report["software"], report["comparison"], report["counts"]
    lines = [
        "# 论文补充日期与最新软件数据的差异",
        "",
        f"对照软件提交 `{sw['commit']}`（{sw['commit_date'][:10]}），从干净 checkout 依次运行 "
        + "、".join(f"`{c}`" for c in sw["build"]) + f" 后得到 {sw['index_records']:,} 条记录。"
        f"逐条比较 Figure 6 的 {report['population']:,} 条冻结来源记录的发布日期：",
        "",
        "| 比较结果 | 数量 |",
        "| --- | ---: |",
        f"| 日期相同 | {cmp['same_date']} |",
        f"| 两边均无日期 | {cmp['both_undated']} |",
        f"| **论文有日期、软件无日期** | **{cmp['figure_dated_software_undated']}** |",
        f"| 两边日期不同 | {cmp['different_date']} |",
        f"| 软件有日期、论文无日期 | {cmp['software_dated_figure_undated']} |",
        "",
        "两边都有日期时全部一致，软件数据仍是其已有日期的依据。"
        f"本文件记录其余 {cmp['figure_dated_software_undated']} 条：它们的日期只来自论文仓库已审核的补充层，"
        "软件仓库的来源爬取、`data/catalog/benchmark_dates.yml` 与 `data/model_cards.yml` 都没有这些日期。",
        "",
        "## 日期如何得到",
        "",
        "| 来源 | 数量 | 输入与字段 | 方法 |",
        "| --- | ---: | --- | --- |",
        f"| Library | {counts['evidence_source'].get('library', 0)} | "
        "`library-reviewed-dates.json` 的 `releaseEvidence.date` | "
        "`match_library_dates.py` 按 catalog/sourceId 精确匹配，或依 `library-date-match-reviews.json` "
        "的身份审查匹配；只采用正式介绍或发布事件 |",
        f"| 旧核验 | {counts['evidence_source'].get('legacy_next_verification', 0)} | "
        "`156_from_xiaoke_all_passed_en.json` 的 `nextVerification.releaseDate` | "
        "`supplement_taxonomy_dates.py` 仅采用 `release-date-legacy-selection.json` 中精确 key 且状态为 passed 的记录 |",
        "",
        "## 统计",
        "",
        "| 来源记录 | 数量 |",
        "| --- | ---: |",
        *[f"| {k} | {v} |" for k, v in counts["source"].items()],
        "",
        "| 日期精度 | 数量 |",
        "| --- | ---: |",
        *[f"| {k} | {v} |" for k, v in counts["precision"].items()],
        "",
        "| Figure 6 时段 | 数量 |",
        "| --- | ---: |",
        *[f"| {k} | {v} |" for k, v in counts["figure_period"].items()],
        "",
        f"其中 {counts['with_first_score_date']} 条在软件中有 `first_score_reported_at`；"
        "那是模型成绩的报告日期，不是 benchmark 发布日期。",
        "",
        "## 文件",
        "",
        "- [software-release-date-gaps.json](software-release-date-gaps.json)：完整记录、证据、软件端字段与输入哈希。",
        "- [software-release-date-gaps.csv](software-release-date-gaps.csv)：便于审核的逐条表格。",
        "",
        "重新生成或检查（软件 checkout 须先完成上述构建）：",
        "",
        "```bash",
        "python scripts/audit_software_release_dates.py /path/to/benchmark-radar",
        "python scripts/audit_software_release_dates.py /path/to/benchmark-radar --check",
        "```",
        "",
    ]
    return "\n".join(lines)


def outputs(report):
    return {
        OUT_JSON: json.dumps(report, ensure_ascii=False, indent=1) + "\n",
        OUT_CSV: to_csv(report),
        OUT_MD: to_markdown(report),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("software", help="Clean Benchmark Radar checkout after the catalog build")
    parser.add_argument("--check", action="store_true", help="Compare with written files without rewriting")
    args = parser.parse_args()
    report = build(args.software)
    if report["software"]["tracked_input_changes"]:
        raise SystemExit("Software data/ or src/ differs from its commit; use a clean checkout")
    stale = []
    for path, text in outputs(report).items():
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path.relative_to(PAPER)))
        else:
            path.write_text(text)
    if stale:
        print("stale:", ", ".join(stale), file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps({"comparison": report["comparison"], **report["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
