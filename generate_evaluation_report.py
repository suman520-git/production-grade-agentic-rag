import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EVALUATIONS_DIR = ROOT / "evaluations"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def percentage(value):
    return f"{value * 100:.2f}%"


def main():
    completed_runs = sorted(
        path.parent
        for path in EVALUATIONS_DIR.glob("*/summary.json")
    )

    if not completed_runs:
        raise SystemExit("No completed evaluation runs found.")

    final_dir = completed_runs[-1]
    summary = read_json(final_dir / "summary.json")
    dataset = read_json(final_dir / "dataset.json")
    run_info = read_json(final_dir / "run_info.json")

    results = [
        json.loads(line)
        for line in (
            final_dir / "results.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if len(results) != summary["questions_run"]:
        raise ValueError("Result count does not match the summary.")

    if sum(row["case_passed"] for row in results) != summary["cases_passed"]:
        raise ValueError("Pass count does not match the summary.")

    if len({row["id"] for row in results}) != len(results):
        raise ValueError("Duplicate question IDs found.")

    if {row["id"] for row in results} != {
        row["id"] for row in dataset["questions"]
    }:
        raise ValueError("Results do not match the dataset question IDs.")

    # Compare only runs using the exact same dataset file.
    comparable_runs = []

    for directory in completed_runs:
        info_path = directory / "run_info.json"

        if not info_path.exists():
            continue

        info = read_json(info_path)

        if info["dataset_sha256"] == run_info["dataset_sha256"]:
            comparable_runs.append(
                (directory.name, read_json(directory / "summary.json"))
            )

    lines = [
        "# Production-Grade Agentic RAG: Evaluation Report",
        "",
        "## Final measured result",
        "",
        (
            f"Automated checks passed for "
            f"{summary['cases_passed']} of "
            f"{summary['questions_run']} questions "
            f"({percentage(summary['case_pass_rate'])})."
        ),
        "",
        f"- Final run: `{final_dir.name}`",
        f"- API target: `{run_info['api_url']}`",
        f"- Judge model: `{run_info['judge_model']}`",
        f"- Dataset SHA-256: `{run_info['dataset_sha256']}`",
        "",
        (
            "This is a development regression evaluation. The same "
            "questions were used to diagnose failures and improve prompts. "
            "It is not an independent held-out accuracy measurement."
        ),
        "",
        "## Dataset",
        "",
        f"Reference documents: {len(dataset['reference_documents'])}.",
        "",
        "| Question group | Count |",
        "|---|---:|",
    ]

    for group, count in Counter(
        question["group"] for question in dataset["questions"]
    ).items():
        lines.append(f"| {group} | {count} |")

    lines += [
        "",
        "## Comparable evaluation runs",
        "",
        "| Run | Passed | Pass rate | Mean chat ms | P95 chat ms |",
        "|---|---:|---:|---:|---:|",
    ]

    for run_id, metrics in comparable_runs:
        lines.append(
            f"| {run_id} "
            f"| {metrics['cases_passed']}/{metrics['questions_run']} "
            f"| {percentage(metrics['case_pass_rate'])} "
            f"| {metrics['successful_chat_mean_ms']:.2f} "
            f"| {metrics['successful_chat_p95_ms']:.2f} |"
        )

    lines += [
        "",
        "## Final metrics",
        "",
        "| Metric | Result |",
        "|---|---:|",
    ]

    rate_metrics = [
        ("Status accuracy", "status_accuracy"),
        ("Hybrid document recall", "hybrid_document_recall"),
        ("Expected-fact coverage", "mean_expected_fact_coverage"),
        (
            "Citation validity on answerable cases",
            "citation_valid_rate_on_answerable_cases",
        ),
        (
            "Grounding pass rate on answerable cases",
            "grounding_pass_rate_on_answerable_cases",
        ),
        ("Abstention pass rate", "abstention_case_pass_rate"),
        ("Greeting pass rate", "greeting_case_pass_rate"),
    ]

    for label, key in rate_metrics:
        lines.append(f"| {label} | {percentage(summary[key])} |")

    lines.append(
        f"| Hybrid document MRR | {summary['hybrid_document_mrr']:.4f} |"
    )

    for label, key in [
        ("Chat errors", "chat_errors"),
        ("Retrieval errors", "retrieval_errors"),
        ("Judge errors", "judge_errors"),
    ]:
        lines.append(f"| {label} | {summary[key]} |")

    lines += [
        "",
        "## Measurement definitions",
        "",
        "- Status accuracy compares the API status with the reference label.",
        (
            "- Retrieval recall and MRR apply to the 30 answerable cases. "
            "They use a separate original-query /search/hybrid request. "
            "Document IDs are deduplicated from the top five returned chunks."
        ),
        (
            "- These retrieval metrics do not measure the graph's final "
            "retrieval after rewriting, reranking, and grading."
        ),
        (
            "- Fact coverage is the mean fraction of required facts "
            "recognized by an LLM judge for each answerable case."
        ),
        (
            "- Citation validation checks inline IDs, returned source IDs, "
            "and their document IDs and content against stored SQL chunks."
        ),
        (
            "- Grounding combines citation validity with an LLM judgment "
            "that the cited evidence supports the answer."
        ),
        (
            "- Answerable-case metrics include all 30 answerable questions. "
            "An abstention or processing failure counts as a failure."
        ),
        (
            "- Abstention checks require the abstained status, grounded=false, "
            "and no sources. Greeting checks require the expected two-node "
            "trace and no retrieval."
        ),
        (
            "- Chat latency is measured by the client and includes any "
            "rate-limit retry wait. It excludes separate retrieval and "
            "external judge calls. It mixes greetings, abstentions, "
            "and document answers."
        ),
        "",
        "## Corrections made during development",
        "",
        (
            "The baseline failed q015, q026, and q028 because supported "
            "policy corrections were rejected. Generation, grounding, "
            "and answer-evaluation prompts were clarified to distinguish "
            "contradicting a question's premise from lacking evidence."
        ),
        "",
        (
            "The next run failed q022 because grounding rejected currency "
            "information explicitly represented by the notation INR. "
            "The grounding prompt was clarified to accept direct extraction "
            "of written units and currency codes."
        ),
        "",
        "## Remaining limitations and manual observations",
        "",
        (
            "- Only three short reference policies are covered. Several "
            "questions are paraphrases, so these 50 cases are not 50 "
            "independent policy scenarios."
        ),
        (
            "- The missing-evidence questions are scoped to the leave "
            "document. Filter-exclusion cases deliberately combine an HR "
            "document ID with an incompatible category."
        ),
        (
            "- LLM judgments can vary and can incorrectly accept or reject "
            "an answer. The judge uses the application's configured model, "
            "so their errors may be correlated."
        ),
        (
            "- q015 uses prohibition wording stronger than the literal "
            "two-day allowance. Describing the documented allowance would "
            "be more cautious."
        ),
        (
            "- q022 expands INR to Indian Rupees even though that expansion "
            "is not written in the source. A strictly extractive answer "
            "would preserve INR."
        ),
        (
            "- No independent held-out dataset, concurrent load test, "
            "or AWS performance test is represented by these results."
        ),
        (
            "- This report does not establish zero hallucinations, "
            "production-wide accuracy, or production readiness."
        ),
        "",
        "## Failed cases in the final run",
        "",
    ]

    failed_ids = summary["failed_case_ids"]
    lines.append(
        ", ".join(failed_ids)
        if failed_ids
        else "None under the automated checks used in this run."
    )

    lines += [
        "",
        "## Evidence files",
        "",
        f"- Run directory: `evaluations/{final_dir.name}/`",
        "- `dataset.json`: reference questions and document snapshot.",
        "- `run_info.json`: run metadata and dataset fingerprint.",
        "- `results.jsonl`: individual API responses and judgments.",
        "- `summary.json`: aggregate metrics.",
        "",
        (
            "Retain the earlier run directories to preserve the measured "
            "development history."
        ),
        "",
    ]

    report_path = final_dir / "evaluation_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Final run: {final_dir.name}")
    print(f"Comparable runs: {len(comparable_runs)}")
    print(
        f"Verified results: "
        f"{summary['cases_passed']}/{len(results)} passed"
    )
    print(f"Report saved: {report_path}")
    print("No API or OpenAI requests were made.")


if __name__ == "__main__":
    main()