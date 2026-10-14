import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EVALUATIONS_DIR = ROOT / "evaluations"

# Only consider completed runs containing a summary.
completed_runs = sorted(
    path.parent
    for path in EVALUATIONS_DIR.glob("*/summary.json")
)

if not completed_runs:
    raise SystemExit("No completed evaluation runs were found.")

run_dir = completed_runs[-1]

summary = json.loads(
    (run_dir / "summary.json").read_text(encoding="utf-8")
)

failed_ids = set(summary["failed_case_ids"])

print(f"Inspecting: {run_dir}")
print(f"Failed cases: {len(failed_ids)}")

with (run_dir / "results.jsonl").open(
    encoding="utf-8"
) as file:
    for line in file:
        if not line.strip():
            continue

        result = json.loads(line)

        if result["id"] not in failed_ids:
            continue

        details = {
            "id": result["id"],
            "question": result["request"]["question"],
            "expected_status": result["expected_status"],
            "expected_facts": result["expected_facts"],
            "retrieval_metrics": result.get("retrieval_metrics"),
            "chat": result["chat"],
            "fact_coverage": result.get("fact_coverage"),
            "citation_valid": result.get("citation_valid"),
            "expected_source_cited": result.get(
                "expected_source_cited"
            ),
            "grounding_passed": result.get("grounding_passed"),
            "judgment": result.get("judgment"),
            "judge_error": result.get("judge_error"),
        }

        print("\n" + "=" * 60)
        print(json.dumps(details, indent=2, ensure_ascii=False))