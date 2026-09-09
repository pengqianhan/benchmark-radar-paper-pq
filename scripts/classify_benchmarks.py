#!/usr/bin/env python3
"""Assign a two-level taxonomy to every benchmark record in the frozen census.

Population anchor: `evidence/catalog-findings.json`, the paper's frozen census of
1,283 source records across four sources. Every record in that file gets exactly
one output row, and no row is created for anything outside it. A record whose
evidence supports no label is written with L1 `other`, never dropped.

Label evidence: the released v0.10.0 crawl CSVs and the tracked model-report
registry. Each label records the source field and the exact token that produced
it, so a reader can check any assignment against the crawl.

The normalized `benchmark-index.json` `categories` field is deliberately NOT an
input. It flattens four OpenCompass columns with different meanings into one
list: 448 records carry `Unsupported`, which is the `support_online_eval` flag,
66 carry `Open-Source`, which is `certificate_level`, 221 carry `LLM` and 127
`VLM`, which name the model type, and `topic_tags` contribute conference venues.
This script reads those columns separately and keeps the non-topical ones out.

Usage:
    python3 scripts/classify_benchmarks.py            # write outputs
    python3 scripts/classify_benchmarks.py --check    # verify committed outputs
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from taxonomy import (  # noqa: E402
    FIELD_WEIGHT,
    GENERIC_MULTIPLIER,
    L1,
    L1_PRIORITY,
    GENERIC_L2,
    L2,
    LAYER_DOMAINS,
    NOISE,
    SUBJECT_DOMAINS,
    SUBJECT_OVERRIDE_RATIO,
    TEXT_PATTERNS,
    TOKEN_MAP,
)

PAPER = Path(__file__).resolve().parents[1]

# Byte-identical copies of the v0.10.0 release crawls and the tracked model-card
# registry, vendored so this repository classifies without a software checkout
# and without the release tree, which .gitignore excludes. `inputs_sha256` in the
# summary pins them; they are frozen inputs, not a second source of truth.
CENSUS = PAPER / "evidence" / "catalog-findings.json"
VENDORED = PAPER / "evidence" / "taxonomy-inputs"
INPUTS = {
    "census": CENSUS,
    "oc": VENDORED / "opencompass_hub_catalog_2026-08-17.csv",
    "ls": VENDORED / "llm_stats_benchmarks_2026-08-17.csv",
    "aa": VENDORED / "artificial_analysis_benchmarks_2026-08-25.csv",
    "mc": VENDORED / "model_cards.yml",
}
OUT_JSONL = PAPER / "evidence" / "benchmark-taxonomy.jsonl"
OUT_SUMMARY = PAPER / "evidence" / "benchmark-taxonomy-summary.json"
# Manuscript macros, so the prose in Section 4.2 cannot drift from the figures.
OUT_MACROS = PAPER / "taxonomy-data.tex"

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def split_pipe(value):
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def split_json_list(value):
    try:
        parsed = json.loads(value or "[]")
    except (ValueError, TypeError):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def load_model_cards(path):
    """Read the benchmark registry out of model_cards.yml without a YAML dep.

    Only the top-level `benchmarks:` list is needed, and only its `id`, `name`,
    `domain`, `url` and `caveat` scalars, so a small line reader keeps this
    script runnable in a bare checkout.
    """
    try:
        import yaml
    except ImportError:
        yaml = None
    if yaml is not None:
        return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["benchmarks"]
    entries, current, in_block, block_key = [], None, False, None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if raw.startswith("model_cards:"):
            break
        item = re.match(r"^  - id: (\S+)", raw)
        if item:
            if current:
                entries.append(current)
            current, in_block = {"id": item.group(1)}, False
            continue
        if current is None:
            continue
        field = re.match(r"^    (\w+): (.*)$", raw)
        if field:
            key, value = field.group(1), field.group(2).strip()
            if value in (">-", "|", ">", "|-"):
                in_block, block_key, current[key] = True, key, ""
            else:
                in_block = False
                current[key] = value.strip("'\"")
            continue
        if in_block and raw.startswith("      "):
            current[block_key] = (current[block_key] + " " + raw.strip()).strip()
    if current:
        entries.append(current)
    return entries


def gather_evidence():
    """Return {census_key: [(field, token), ...]} plus per-record free text."""
    tags = defaultdict(list)
    text = {}

    for row in read_csv(INPUTS["oc"]):
        key = f"opencompass:{row['benchmark_id']}"
        for field in ("dimensions", "basic_tags", "card_tags", "topic_tags"):
            for token in split_pipe(row.get(field)):
                tags[key].append((f"oc.{field}", token))
        text[key] = " ".join(
            filter(None, [
                row.get("name"), row.get("card_description_en"),
                row.get("detail_description_en"), row.get("detail_title"),
            ])
        )

    for row in read_csv(INPUTS["ls"]):
        key = f"llm-stats:{row['benchmark_id']}"
        for token in split_json_list(row.get("categories")):
            tags[key].append(("ls.categories", token))
        for token in split_json_list(row.get("detail_categories")):
            if ("ls.categories", token) not in tags[key]:
                tags[key].append(("ls.categories", token))
        if row.get("modality"):
            tags[key].append(("ls.modality", row["modality"]))
        text[key] = " ".join(filter(None, [row.get("name"), row.get("description")]))

    for row in read_csv(INPUTS["aa"]):
        key = f"artificial-analysis:{row['benchmark_id']}"
        for token in split_json_list(row.get("categories")):
            tags[key].append(("aa.categories", token))
        if row.get("modality"):
            tags[key].append(("aa.modality", row["modality"]))
        text[key] = " ".join(filter(None, [row.get("name"), row.get("description")]))

    for entry in load_model_cards(INPUTS["mc"]):
        key = f"model-reports:{entry['id']}"
        if entry.get("domain"):
            tags[key].append(("mc.domain", entry["domain"]))
        text[key] = " ".join(filter(None, [entry.get("name"), entry.get("caveat")]))

    return tags, text


def l1_score(votes):
    """Collapse one L1's L2 votes into a single score with diminishing returns.

    Repeated evidence for the *same* L2 reinforces it, so each bucket keeps its
    strongest token. Evidence for *different* L2s under one L1 signals breadth
    rather than depth -- `legal` plus `finance` does not make a benchmark twice
    as vertical -- so the second bucket counts half, the third a third, and so on.
    """
    ordered = sorted(votes.values(), reverse=True)
    return sum(weight / (rank + 1) for rank, weight in enumerate(ordered))


def pick_l2(votes):
    """Most specific L2 with support; a `*_general` bucket only as a fallback."""
    specific = {l2: weight for l2, weight in votes.items() if l2 not in GENERIC_L2}
    pool = specific or dict(votes)
    return max(sorted(pool), key=lambda l2: pool[l2])


MODALITY_FIELD_FACET = {
    "text": None,  # the default; recorded on the record, not as a facet
    "multimodal": "modality:multimodal",
    "image": "modality:image",
    "video": "modality:video",
    "audio": "modality:audio",
}


def review_reasons(scores, primary, confidence):
    """Name why a row deserves a human read. Empty list means no flag."""
    reasons = []
    if primary == "other":
        return ["unclassified"]
    ranked = scores.most_common()
    if len(ranked) > 1 and ranked[1][1] >= ranked[0][1] * 0.8:
        reasons.append(f"close_runner_up:{ranked[1][0]}")
    if confidence < 0.35:
        reasons.append("low_confidence")
    return reasons


# Census measurements carried through unchanged, so a downstream trend or Sankey
# needs no second join. These are the census's own values; nothing is imputed.
CENSUS_PASSTHROUGH = (
    "slug", "release_date", "score_date_precision",
    "numeric_scores", "model_count", "document_count",
)


def classify(key, source, name, tag_evidence, free_text):
    scores = Counter()
    l2_votes = defaultdict(Counter)
    facets = set()
    provenance = []
    unmapped = []
    declared_modality = None

    for field, token in tag_evidence:
        low = token.strip().lower()
        if field in ("ls.modality", "aa.modality"):
            declared_modality = low
            facet = MODALITY_FIELD_FACET.get(low)
            if facet:
                facets.add(facet)
                provenance.append({"field": field, "token": token, "facet": facet})
            continue
        if low in NOISE:
            provenance.append({"field": field, "token": token, "excluded": NOISE[low]})
            continue
        entry = TOKEN_MAP.get(low)
        if entry is None:
            unmapped.append((field, token))
            continue
        if entry["l1"] is None:
            # A property of the data or the harness, not a capability under test.
            facets.update(entry["facets"])
            provenance.append({"field": field, "token": token, "facets": entry["facets"]})
            continue
        weight = FIELD_WEIGHT.get(field, 1.0) * (GENERIC_MULTIPLIER if entry["generic"] else 1.0)
        bucket = l2_votes[entry["l1"]][entry["l2"]]
        l2_votes[entry["l1"]][entry["l2"]] = max(bucket, weight)
        facets.update(entry["facets"])
        provenance.append({
            "field": field, "token": token, "l1": entry["l1"],
            "l2": entry["l2"], "weight": round(weight, 3),
            "generic": entry["generic"] or None,
        })

    # Text patterns run for every record, at a lower weight than any tag field,
    # so they refine an L2 without overturning a publisher's own dimension.
    haystack = f"{name} {free_text}".lower()
    for pattern, l1, l2, extra, exclude in TEXT_PATTERNS:
        match = re.search(pattern, haystack)
        if not match:
            continue
        if exclude and re.search(exclude, haystack):
            provenance.append({"field": "text.excluded", "token": match.group(0),
                               "pattern": pattern, "excluded_by": exclude})
            continue
        field = "text.name" if re.search(pattern, name.lower()) else "text.description"
        weight = FIELD_WEIGHT[field]
        l2_votes[l1][l2] = max(l2_votes[l1][l2], weight)
        facets.update(extra)
        provenance.append({
            "field": field, "token": match.group(0), "pattern": pattern,
            "l1": l1, "l2": l2, "weight": round(weight, 3),
        })

    scores = Counter({l1: l1_score(votes) for l1, votes in l2_votes.items()})

    unclassified_reason = None
    if not scores:
        primary, primary_l2 = "other", "unclassified"
        confidence = 0.0
        # Say why, rather than letting an empty crawl row look like a judgement.
        # A bare name is not evidence: these rows carried no tag and no prose.
        unclassified_reason = (
            "no_source_evidence" if not tag_evidence else "evidence_present_but_unmapped"
        )
    else:
        best = max(scores.values())
        tied = [l1 for l1, value in scores.items() if abs(value - best) < 1e-9]
        primary = min(tied, key=L1_PRIORITY.index)
        if primary in LAYER_DOMAINS:
            contenders = [
                l1 for l1 in scores
                if l1 in SUBJECT_DOMAINS and scores[l1] >= best * SUBJECT_OVERRIDE_RATIO
            ]
            if contenders:
                overridden = primary
                primary = max(contenders, key=lambda l1: (scores[l1], -L1_PRIORITY.index(l1)))
                provenance.append({
                    "rule": "subject_over_layer",
                    "from": overridden, "to": primary,
                    "ratio": round(scores[primary] / best, 3),
                })
        primary_l2 = pick_l2(l2_votes[primary])
        total = sum(scores.values())
        confidence = round(scores[primary] / total, 3) if total else 0.0

    if declared_modality is None and source == "opencompass_hub":
        declared_modality = "multimodal" if any(
            f == "modality:multimodal" for f in facets
        ) else None

    return {
        "key": key,
        "name": name,
        "source": source,
        "l1": primary,
        "l1_label": L1[primary],
        "l2": primary_l2,
        "l1_all": sorted(scores, key=lambda k: (-scores[k], L1_PRIORITY.index(k))),
        "l1_scores": {k: round(v, 3) for k, v in scores.most_common()},
        "l2_all": sorted({l2 for votes in l2_votes.values() for l2 in votes}),
        "modality": sorted(f.split(":", 1)[1] for f in facets if f.startswith("modality:"))
        or ([declared_modality] if declared_modality else []),
        "interaction": sorted(f.split(":", 1)[1] for f in facets if f.startswith("interaction:")) or ["static"],
        "operational": sorted(f.split(":", 1)[1] for f in facets if f.startswith("op:")),
        "confidence": confidence,
        "needs_review": review_reasons(scores, primary, confidence),
        "unclassified_reason": unclassified_reason,
        "label_basis": "tags" if any(p.get("l1") and p["field"].startswith(("oc.", "ls.", "aa.", "mc."))
                                     for p in provenance) else ("text" if scores else "none"),
        "evidence": provenance,
        "unmapped_tokens": [{"field": f, "token": t} for f, t in unmapped],
    }


def build():
    census = json.loads(CENSUS.read_text(encoding="utf-8"))["records"]
    tags, text = gather_evidence()
    rows = []
    for record in census:
        key = record["key"]
        row = classify(
            key=key,
            source=record["source"],
            name=record["name"],
            tag_evidence=tags.get(key, []),
            free_text=text.get(key, ""),
        )
        row.update({field: record.get(field) for field in CENSUS_PASSTHROUGH})
        rows.append(row)
    return census, rows


def summarise(census, rows):
    by_l1 = Counter(r["l1"] for r in rows)
    by_source_l1 = defaultdict(Counter)
    by_l2 = Counter()
    facets = {axis: Counter() for axis in ("modality", "interaction", "operational")}
    basis = Counter(r["label_basis"] for r in rows)
    unmapped = Counter()
    for row in rows:
        by_source_l1[row["source"]][row["l1"]] += 1
        by_l2[f"{row['l1']}/{row['l2']}"] += 1
        for axis in facets:
            facets[axis].update(row[axis])
        for item in row["unmapped_tokens"]:
            unmapped[f"{item['field']}::{item['token']}"] += 1
    # How each facet spreads over the Level 1 classes. The separation only earns
    # its place if a facet genuinely crosses classes, so the number is published.
    facet_by_l1 = defaultdict(Counter)
    for row in rows:
        for axis in ("modality", "interaction", "operational"):
            for value in row[axis]:
                facet_by_l1[f"{axis}:{value}"][row["l1"]] += 1

    return {
        "schema_version": 1,
        "definitions": {
            "population": "One row per source record in evidence/catalog-findings.json; no name merging, no surface filter.",
            "l1": "Single primary capability domain per record, for one flow per benchmark in a Sankey or stacked area.",
            "l2": "Sub-domain under that L1; a `*_general` value means no more specific evidence was present.",
            "l1_all": "Every L1 that received evidence, strongest first. A record can support several; only `l1` is primary.",
            "modality": "Input types the evidence names. Orthogonal to L1; a text benchmark carries `text`.",
            "interaction": "`agentic` where the evidence names an agent loop, tool call, environment or computer use; otherwise `static`.",
            "operational": "Cross-cutting properties such as long_context, tool_calling, multilingual, safety_probe. Never an L1.",
            "confidence": "Primary L1 weight over total weight. Low values mean competing evidence, not a wrong label.",
            "needs_review": "Reasons a human should read the row: a runner-up within 20 percent, low confidence, or no evidence.",
            "evidence": "Every token that produced a label, with its source field and weight, plus tokens excluded as non-topical.",
            "release_date": "Carried unchanged from the census. 668 records have none and cannot enter a year trend.",
        },
        "population": len(census),
        "classified": len(rows),
        "inputs_sha256": {name: sha256(path) for name, path in INPUTS.items()},
        "taxonomy": {"l1": L1, "l2": L2, "l1_priority": L1_PRIORITY},
        "field_weights": FIELD_WEIGHT,
        "generic_multiplier": GENERIC_MULTIPLIER,
        "by_l1": dict(by_l1.most_common()),
        "by_source_l1": {s: dict(c.most_common()) for s, c in by_source_l1.items()},
        "by_l2": dict(by_l2.most_common()),
        "facets": {axis: dict(c.most_common()) for axis, c in facets.items()},
        "facet_by_l1": {k: dict(v.most_common()) for k, v in sorted(facet_by_l1.items())},
        "label_basis": dict(basis.most_common()),
        "unmapped_tokens": dict(unmapped.most_common()),
    }


def macros(summary):
    """LaTeX definitions for the counts Section 4.2 states in prose."""
    agentic = summary["facet_by_l1"]["interaction:agentic"]
    values = {
        "TaxonomyLevelOneCount": len(summary["by_l1"]),
        "TaxonomyAgenticPrimary": agentic.get("agentic_tool_use", 0),
        "TaxonomyAgenticCoding": agentic.get("coding_se", 0),
        "TaxonomyAgenticOtherClasses": len(agentic) - 2,
        "TaxonomyLevelTwoCount": len(summary["by_l2"]),
        "TaxonomyAgentic": summary["facets"]["interaction"]["agentic"],
        "TaxonomyStatic": summary["facets"]["interaction"]["static"],
        "TaxonomyUnclassified": summary["by_l1"]["other"],
        "TaxonomyLabelledFromTags": summary["label_basis"]["tags"],
    }
    lines = ["% Generated by scripts/classify_benchmarks.py. Do not edit by hand."]
    lines += [f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in values.items()]
    return "\n".join(lines) + "\n"


def audit(census, rows, summary):
    problems = []
    census_keys = [r["key"] for r in census]
    row_keys = [r["key"] for r in rows]
    if len(census_keys) != len(set(census_keys)):
        problems.append("census contains duplicate keys")
    if row_keys != census_keys:
        missing = set(census_keys) - set(row_keys)
        extra = set(row_keys) - set(census_keys)
        problems.append(f"row/census mismatch: {len(missing)} missing, {len(extra)} extra")
    if len(rows) != len(census):
        problems.append(f"classified {len(rows)} of {len(census)} records")
    if len(census) < 1259:
        problems.append(f"population {len(census)} below the 1,259-record baseline")
    if len({r['source'] for r in census}) < 4:
        problems.append("fewer than four sources in the population")
    for row in rows:
        if row["l1"] not in L1:
            problems.append(f"{row['key']}: unknown L1 {row['l1']}")
        if row["l2"] not in L2[row["l1"]]:
            problems.append(f"{row['key']}: L2 {row['l2']} not under L1 {row['l1']}")
        for axis in ("modality", "interaction", "operational"):
            if not isinstance(row[axis], list):
                problems.append(f"{row['key']}: {axis} is not a list")
    if sum(summary["by_l1"].values()) != len(census):
        problems.append("by_l1 does not reconcile to the population")
    for source, counts in summary["by_source_l1"].items():
        expected = sum(1 for r in census if r["source"] == source)
        if sum(counts.values()) != expected:
            problems.append(f"{source}: {sum(counts.values())} classified vs {expected} in census")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify committed outputs match a rebuild")
    args = parser.parse_args()

    census, rows = build()
    summary = summarise(census, rows)
    problems = audit(census, rows, summary)

    written = {
        OUT_JSONL: "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n",
        OUT_SUMMARY: json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        OUT_MACROS: macros(summary),
    }
    if args.check:
        for path, text in written.items():
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                problems.append(f"{path.relative_to(PAPER)} does not match a rebuild")
    else:
        for path, text in written.items():
            path.write_text(text, encoding="utf-8")

    print(f"population {summary['population']}  classified {summary['classified']}")
    print("by L1: " + ", ".join(f"{k}={v}" for k, v in summary["by_l1"].items()))
    print("label basis: " + ", ".join(f"{k}={v}" for k, v in summary["label_basis"].items()))
    if summary["unmapped_tokens"]:
        total = sum(summary["unmapped_tokens"].values())
        print(f"unmapped tokens: {len(summary['unmapped_tokens'])} distinct, {total} occurrences")
        for token, count in list(summary["unmapped_tokens"].items())[:25]:
            print(f"    {count:4d}  {token}")
    if problems:
        print("\nAUDIT FAILED")
        for problem in problems:
            print("  - " + problem)
        return 1
    print("\nAudit passed: every census record classified, counts reconcile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
