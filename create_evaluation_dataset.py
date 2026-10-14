import hashlib
import json
from collections import Counter
from pathlib import Path

from backend.database import get_connection


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "evaluation_questions.json"


# These are the policies already added during development.
# We verify their content before creating reference labels.
POLICIES = {
    "leave": {
        "title": "Annual Leave Policy",
        "category": "hr",
        "content": (
            "Employees receive 20 working days of annual leave each year."
        ),
    },
    "remote": {
        "title": "Remote Work Policy",
        "category": "hr",
        "content": (
            "Employees may work remotely two days per week "
            "with manager approval."
        ),
    },
    "training": {
        "title": "Training Budget Policy",
        "category": "hr",
        "content": (
            "Employees may claim up to INR 10000 per year for approved "
            "training courses. Manager approval is required before enrollment."
        ),
    },
}


def load_policy_documents():
    """Resolve real document IDs and verify the expected evidence."""
    documents = {}

    with get_connection() as connection:
        with connection.cursor() as cursor:
            for key, policy in POLICIES.items():
                cursor.execute(
                    """
                    SELECT id, content, indexed
                    FROM documents
                    WHERE title = %s AND category = %s
                    ORDER BY id
                    """,
                    (policy["title"], policy["category"]),
                )

                rows = cursor.fetchall()

                if len(rows) != 1:
                    raise ValueError(
                        f"Expected exactly one document named "
                        f"{policy['title']!r} in category 'hr'; "
                        f"found {len(rows)}."
                    )

                document_id, content, indexed = rows[0]

                if content.strip() != policy["content"]:
                    raise ValueError(
                        f"Content differs for {policy['title']!r}. "
                        "Review the policy and reference answers "
                        "before creating the dataset."
                    )

                if not indexed:
                    raise ValueError(
                        f"{policy['title']!r} is not indexed. "
                        f"Index document {document_id} first."
                    )

                documents[key] = {
                    "document_id": document_id,
                    "title": policy["title"],
                    "category": policy["category"],
                    "content": content,
                    "content_sha256": hashlib.sha256(
                        content.encode("utf-8")
                    ).hexdigest(),
                }

    return documents


def build_questions(documents):
    questions = []

    def add(
        group,
        question,
        expected_status,
        expected_facts=None,
        relevant_policy=None,
        category=None,
        document_id=None,
    ):
        relevant_ids = []

        if relevant_policy is not None:
            relevant_ids = [
                documents[relevant_policy]["document_id"]
            ]

        questions.append(
            {
                "id": f"q{len(questions) + 1:03d}",
                "group": group,
                "request": {
                    "question": question,
                    "top_k": 5,
                    "category": category,
                    "document_id": document_id,
                },
                "expected_status": expected_status,
                "expected_facts": expected_facts or [],
                "relevant_document_ids": relevant_ids,
                "requires_citations": expected_status == "answered",
            }
        )

    # 10 annual leave questions.
    leave_questions = [
        "How many annual leave days do employees receive?",
        "What is the yearly annual leave entitlement?",
        "How much annual leave does an employee get each year?",
        "Does the annual leave allowance use working days?",
        "Is annual leave provided every year?",
        "Tell me the number and type of annual leave days provided.",
        "Do employees receive 20 working days of annual leave each year?",
        "Do employees receive 25 working days of annual leave each year?",
        "Hello, how many annual leave days do employees receive?",
        "According to the leave policy, what is the annual entitlement?",
    ]

    leave_facts = [
        "Employees receive 20 working days of annual leave each year."
    ]

    for question in leave_questions:
        add(
            group="annual_leave",
            question=question,
            expected_status="answered",
            expected_facts=leave_facts,
            relevant_policy="leave",
            category="hr",
        )

    # 10 remote work questions with question-specific facts.
    remote_cases = [
        (
            "How many days per week may employees work remotely?",
            ["Employees may work remotely two days per week."],
        ),
        (
            "What approval is required for remote work?",
            ["Manager approval is required for remote work."],
        ),
        (
            "What is the remote work policy?",
            [
                "Employees may work remotely two days per week.",
                "Manager approval is required.",
            ],
        ),
        (
            "Can employees work remotely two days per week?",
            [
                "Employees may work remotely two days per week.",
                "Manager approval is required.",
            ],
        ),
        (
            "Does the policy permit three remote work days per week?",
            ["The policy permits two remote work days per week, not three."],
        ),
        (
            "Can employees work remotely without manager approval?",
            ["Manager approval is required for remote work."],
        ),
        (
            "Who must approve remote work?",
            ["The employee's manager must approve remote work."],
        ),
        (
            "What is the weekly remote work allowance?",
            ["Employees may work remotely two days per week."],
        ),
        (
            "Hello, what approval do I need to work remotely?",
            ["Manager approval is required for remote work."],
        ),
        (
            "State both the remote work limit and the approval requirement.",
            [
                "Employees may work remotely two days per week.",
                "Manager approval is required.",
            ],
        ),
    ]

    for question, facts in remote_cases:
        add(
            group="remote_work",
            question=question,
            expected_status="answered",
            expected_facts=facts,
            relevant_policy="remote",
            category="hr",
        )

    # 10 training budget questions.
    training_cases = [
        (
            "What is the maximum annual training claim?",
            ["Employees may claim up to INR 10000 per year."],
        ),
        (
            "What currency is used for the training budget?",
            ["The training budget is stated in INR."],
        ),
        (
            "Who must approve a training course?",
            ["Manager approval is required."],
        ),
        (
            "When must training approval be obtained?",
            ["Manager approval is required before enrollment."],
        ),
        (
            "Can employees claim training expenses for any course?",
            ["Training claims apply to approved training courses."],
        ),
        (
            "Does the policy allow an annual training claim of INR 15000?",
            ["The annual training claim limit is INR 10000, not INR 15000."],
        ),
        (
            "Is the INR 10000 training allowance monthly or yearly?",
            ["The INR 10000 training claim limit applies per year."],
        ),
        (
            "Can I enroll first and obtain manager approval afterward?",
            ["Manager approval is required before enrollment."],
        ),
        (
            "What is the annual training budget and what approval is required?",
            [
                "Employees may claim up to INR 10000 per year "
                "for approved training courses.",
                "Manager approval is required before enrollment.",
            ],
        ),
        (
            "Hello, summarize the training reimbursement policy.",
            [
                "Employees may claim up to INR 10000 per year "
                "for approved training courses.",
                "Manager approval is required before enrollment.",
            ],
        ),
    ]

    for question, facts in training_cases:
        add(
            group="training_budget",
            question=question,
            expected_status="answered",
            expected_facts=facts,
            relevant_policy="training",
            category="hr",
        )

    # These questions are deliberately restricted to the leave document.
    # That document contains none of the requested information.
    # The restriction keeps these labels valid if other policies are added.
    unknown_questions = [
        "What is the company's laptop replacement policy?",
        "What is the office Wi-Fi password?",
        "How many sick leave days do employees receive?",
        "Can unused annual leave be carried forward?",
        "What is the company's maternity leave entitlement?",
        "What is the employee notice period?",
        "What health insurance coverage do employees receive?",
        "When are employee salaries paid?",
        "Who is the head of the IT department?",
        "What is the business travel meal reimbursement limit?",
    ]

    for question in unknown_questions:
        add(
            group="missing_evidence",
            question=question,
            expected_status="abstained",
            category="hr",
            document_id=documents["leave"]["document_id"],
        )

    # The selected documents belong to HR.
    # Combining their IDs with another category must return no evidence.
    filter_cases = [
        (
            "leave",
            "it",
            "How many annual leave days do employees receive?",
        ),
        (
            "leave",
            "finance",
            "What is the yearly annual leave entitlement?",
        ),
        (
            "remote",
            "it",
            "How many days per week may employees work remotely?",
        ),
        (
            "remote",
            "general",
            "Who must approve remote work?",
        ),
        (
            "training",
            "finance",
            "What is the maximum annual training claim?",
        ),
    ]

    for policy_key, category, question in filter_cases:
        add(
            group="filter_exclusion",
            question=question,
            expected_status="abstained",
            category=category,
            document_id=documents[policy_key]["document_id"],
        )

    # All greetings meet the API's minimum question length.
    for question in ["Hello", "hello", "HELLO", "Hello!", "Hello."]:
        add(
            group="greeting",
            question=question,
            expected_status="direct_answer",
        )

    return questions


def main():
    documents = load_policy_documents()
    questions = build_questions(documents)

    if len(questions) != 50:
        raise ValueError(
            f"Expected 50 questions; generated {len(questions)}."
        )

    ids = [question["id"] for question in questions]

    if len(ids) != len(set(ids)):
        raise ValueError("Question IDs must be unique.")

    dataset = {
        "dataset_version": 1,
        "description": (
            "Baseline evaluation for policy answers, citations, "
            "abstention, metadata filters, and greeting routing."
        ),
        "reference_documents": list(documents.values()),
        "questions": questions,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_PATH.write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Dataset saved: {OUTPUT_PATH}")
    print(f"Reference documents: {len(documents)}")
    print(f"Questions: {len(questions)}")

    print("\nQuestion groups:")
    for group, count in Counter(
        item["group"] for item in questions
    ).items():
        print(f"  {group}: {count}")

    print("\nExpected statuses:")
    for status, count in Counter(
        item["expected_status"] for item in questions
    ).items():
        print(f"  {status}: {count}")

    print("\nNo OpenAI requests were made.")


if __name__ == "__main__":
    main()