# Production-Grade Agentic RAG: Evaluation Report

## Final measured result

Automated checks passed for 50 of 50 questions (100.00%).

- Final run: `20261014T121238454739Z`
- API target: `http://127.0.0.1:8000`
- Judge model: `gpt-4o-mini`
- Dataset SHA-256: `aa1fad8dbc43d308b89918402115a5e30ad6801e857b3b7f37041460e3fee6d6`

This is a development regression evaluation. The same questions were used to diagnose failures and improve prompts. It is not an independent held-out accuracy measurement.

## Dataset

Reference documents: 3.

| Question group | Count |
|---|---:|
| annual_leave | 10 |
| remote_work | 10 |
| training_budget | 10 |
| missing_evidence | 10 |
| filter_exclusion | 5 |
| greeting | 5 |

## Comparable evaluation runs

| Run | Passed | Pass rate | Mean chat ms | P95 chat ms |
|---|---:|---:|---:|---:|
| 20261014T102357916308Z | 47/50 | 94.00% | 5491.26 | 8327.99 |
| 20261014T115101277889Z | 49/50 | 98.00% | 5538.55 | 7898.55 |
| 20261014T121238454739Z | 50/50 | 100.00% | 5620.18 | 8041.03 |

## Final metrics

| Metric | Result |
|---|---:|
| Status accuracy | 100.00% |
| Hybrid document recall | 100.00% |
| Expected-fact coverage | 100.00% |
| Citation validity on answerable cases | 100.00% |
| Grounding pass rate on answerable cases | 100.00% |
| Abstention pass rate | 100.00% |
| Greeting pass rate | 100.00% |
| Hybrid document MRR | 1.0000 |
| Chat errors | 0 |
| Retrieval errors | 0 |
| Judge errors | 0 |

## Measurement definitions

- Status accuracy compares the API status with the reference label.
- Retrieval recall and MRR apply to the 30 answerable cases. They use a separate original-query /search/hybrid request. Document IDs are deduplicated from the top five returned chunks.
- These retrieval metrics do not measure the graph's final retrieval after rewriting, reranking, and grading.
- Fact coverage is the mean fraction of required facts recognized by an LLM judge for each answerable case.
- Citation validation checks inline IDs, returned source IDs, and their document IDs and content against stored SQL chunks.
- Grounding combines citation validity with an LLM judgment that the cited evidence supports the answer.
- Answerable-case metrics include all 30 answerable questions. An abstention or processing failure counts as a failure.
- Abstention checks require the abstained status, grounded=false, and no sources. Greeting checks require the expected two-node trace and no retrieval.
- Chat latency is measured by the client and includes any rate-limit retry wait. It excludes separate retrieval and external judge calls. It mixes greetings, abstentions, and document answers.

## Corrections made during development

The baseline failed q015, q026, and q028 because supported policy corrections were rejected. Generation, grounding, and answer-evaluation prompts were clarified to distinguish contradicting a question's premise from lacking evidence.

The next run failed q022 because grounding rejected currency information explicitly represented by the notation INR. The grounding prompt was clarified to accept direct extraction of written units and currency codes.

## Remaining limitations and manual observations

- Only three short reference policies are covered. Several questions are paraphrases, so these 50 cases are not 50 independent policy scenarios.
- The missing-evidence questions are scoped to the leave document. Filter-exclusion cases deliberately combine an HR document ID with an incompatible category.
- LLM judgments can vary and can incorrectly accept or reject an answer. The judge uses the application's configured model, so their errors may be correlated.
- q015 uses prohibition wording stronger than the literal two-day allowance. Describing the documented allowance would be more cautious.
- q022 expands INR to Indian Rupees even though that expansion is not written in the source. A strictly extractive answer would preserve INR.
- No independent held-out dataset, concurrent load test, or AWS performance test is represented by these results.
- This report does not establish zero hallucinations, production-wide accuracy, or production readiness.

## Failed cases in the final run

None under the automated checks used in this run.

## Evidence files

- Run directory: `evaluations/20261014T121238454739Z/`
- `dataset.json`: reference questions and document snapshot.
- `run_info.json`: run metadata and dataset fingerprint.
- `results.jsonl`: individual API responses and judgments.
- `summary.json`: aggregate metrics.

Retain the earlier run directories to preserve the measured development history.
