from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "data" / "tool_selection_cases.json"
TARGET_TOOLS = (
    "england_works_watch_info",
    "licensing_source_status",
    "list_supported_change_events",
    "assess_change_impact",
    "batch_assess_changes",
)

# Frozen pre-benchmark production descriptions. Keeping the old metadata here
# makes improvement measurable and prevents a future rewrite from silently
# redefining the baseline.
BASELINE_DESCRIPTIONS: dict[str, str] = {
    "england_works_watch_info": "Free product scope, supported events, prices and payment/discovery metadata.",
    "licensing_source_status": "Free official-source lifecycle, fingerprint, freshness and review status.",
    "list_supported_change_events": "Free list of V0.1 sponsor change event types.",
    "assess_change_impact": "Paid deterministic Skilled Worker sponsor change-impact preflight. Requires x402 USDC payment.",
    "batch_assess_changes": "Paid batch change-impact preflight for 1..25 sponsor events. Requires x402 USDC payment.",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _ngrams(text: str) -> Counter[str]:
    toks = _tokens(text)
    grams = list(toks)
    grams.extend(f"{a} {b}" for a, b in zip(toks, toks[1:]))
    return Counter(grams)


def _idf(documents: list[Counter[str]]) -> dict[str, float]:
    n = len(documents)
    df: Counter[str] = Counter()
    for doc in documents:
        df.update(doc.keys())
    return {term: math.log((1 + n) / (1 + freq)) + 1.0 for term, freq in df.items()}


def _vector(counter: Counter[str], idf: dict[str, float]) -> dict[str, float]:
    if not counter:
        return {}
    total = sum(counter.values())
    return {term: (count / total) * idf.get(term, 1.0) for term, count in counter.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(value * b.get(term, 0.0) for term, value in a.items())
    na = math.sqrt(sum(value * value for value in a.values()))
    nb = math.sqrt(sum(value * value for value in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def score(tools: dict[str, str], cases: list[dict[str, str]]) -> dict[str, object]:
    missing = sorted(set(TARGET_TOOLS) - set(tools))
    if missing:
        raise SystemExit(f"missing tool descriptions: {missing}")
    tool_counters = {name: _ngrams(tools[name]) for name in TARGET_TOOLS}
    all_counters = list(tool_counters.values()) + [_ngrams(case["query"]) for case in cases]
    idf = _idf(all_counters)
    tool_vectors = {name: _vector(counter, idf) for name, counter in tool_counters.items()}
    results = []
    correct = 0
    for case in cases:
        qvec = _vector(_ngrams(case["query"]), idf)
        scores = {name: _cosine(qvec, vector) for name, vector in tool_vectors.items()}
        predicted = max(scores, key=scores.get)
        expected = case["expected_tool"]
        ok = predicted == expected
        correct += int(ok)
        results.append(
            {
                "query": case["query"],
                "expected_tool": expected,
                "predicted_tool": predicted,
                "correct": ok,
                "scores": dict(sorted(scores.items(), key=lambda item: item[1], reverse=True)),
            }
        )
    total = len(cases)
    return {
        "correct": correct,
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "results": results,
    }


def run() -> dict[str, object]:
    sys.path.insert(0, str(ROOT / "src"))
    from england_works_watch.selection_metadata import TOOL_SELECTION_DESCRIPTIONS

    benchmark = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = benchmark["cases"]
    baseline = score(BASELINE_DESCRIPTIONS, cases)
    effective = score(TOOL_SELECTION_DESCRIPTIONS, cases)
    return {
        "benchmark": benchmark["benchmark"],
        "metric": "top1_tool_selection_accuracy",
        "baseline": baseline,
        "effective": effective,
        "delta": effective["accuracy"] - baseline["accuracy"],
        "gate": {
            "minimum_effective_accuracy": 0.95,
            "must_improve_over_baseline": True,
        },
        "caveat": "Deterministic lexical proxy only; real-agent/model evaluation remains a separate external-validity gate.",
    }


def main() -> None:
    report = run()
    baseline = report["baseline"]
    effective = report["effective"]
    print(json.dumps(report, indent=2, sort_keys=True))
    if float(effective["accuracy"]) < 0.95:
        raise SystemExit("Selection benchmark failed: effective accuracy below 95%")
    if float(effective["accuracy"]) <= float(baseline["accuracy"]):
        raise SystemExit("Selection benchmark failed: no improvement over frozen baseline")
    print(
        "ENGLAND_TOOL_SELECTION_BENCHMARK=PASS "
        f"baseline={baseline['correct']}/{baseline['total']} "
        f"effective={effective['correct']}/{effective['total']}"
    )


if __name__ == "__main__":
    main()
