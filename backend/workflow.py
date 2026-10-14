from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from backend.generation import generate_answer, ABSTENTION
from backend.grader import grade_chunks
from backend.grounding import check_grounding
from backend.hybrid_search import search_hybrid
from backend.reranker import rerank_chunks
from backend.rewriter import rewrite_query
from backend.schemas import AnswerResult, GroundingResult

from backend.query_analysis import analyze_query
from backend.answer_evaluation import evaluate_answer

from time import perf_counter
from uuid import uuid4

from backend.observability import log_event, traced_node

# One rewrite means at most two retrieval attempts.
MAX_REWRITES = 1


class RAGState(TypedDict, total=False):
    question: str
    search_query: str
    top_k: int
    document_id: int | None

    rewrite_count: int
    retrieval_attempts: int

    candidates: list[dict]
    ranked: list[dict]
    evidence: list[dict]

    draft: AnswerResult
    grounding: GroundingResult

    trace: list[str]
    response: dict
    intent: str
    route: str

    evaluation: dict

    category: str | None

    retrieval_degraded: bool
    request_id: str




def retrieve_node(state: RAGState):
    candidates = search_hybrid(
        question=state["search_query"],
        top_k=10,
        document_id=state["document_id"],
        category=state["category"],
    )

    used_fallback = any(
        chunk.get("retrieval_mode") == "keyword_fallback"
        for chunk in candidates
    )

    return {
        "candidates": candidates,
        "retrieval_attempts": state["retrieval_attempts"] + 1,
        "retrieval_degraded": (
            state["retrieval_degraded"] or used_fallback
        ),
        "trace": state["trace"] + ["retrieve"],
    }


def rerank_node(state: RAGState):
    # Judge usefulness against the ORIGINAL question.
    ranked = rerank_chunks(
        state["question"],
        state["candidates"],
    )

    return {
        "ranked": ranked,
        "trace": state["trace"] + ["rerank"],
    }


def grade_node(state: RAGState):
    graded = grade_chunks(
        state["question"],
        state["ranked"],
    )

    evidence = graded["relevant_chunks"][:state["top_k"]]

    return {
        "evidence": evidence,
        "trace": state["trace"] + ["grade"],
    }


def route_after_grade(state: RAGState):
    if state["evidence"]:
        return "generate"

    if state["rewrite_count"] < MAX_REWRITES:
        return "rewrite"

    # No evidence after the allowed retry.
    # generate_answer() already returns an abstention for empty evidence.
    return "generate"


def rewrite_node(state: RAGState):
    search_query = rewrite_query(
        question=state["question"],
        previous_query=state["search_query"],
    )

    return {
        "search_query": search_query,
        "rewrite_count": state["rewrite_count"] + 1,
        "trace": state["trace"] + ["rewrite"],
    }


def generate_node(state: RAGState):
    draft = generate_answer(
        state["question"],
        state["evidence"],
    )

    return {
        "draft": draft,
        "trace": state["trace"] + ["generate"],
    }


def grounding_node(state: RAGState):
    grounding = check_grounding(
        state["question"],
        state["draft"],
        state["evidence"],
    )

    return {
        "grounding": grounding,
        "trace": state["trace"] + ["grounding"],
    }


def finish_node(state: RAGState):
    draft = state["draft"]
    grounding = state["grounding"]
    evaluation = state["evaluation"]
    answered = (
    draft.can_answer
    and grounding.supported
    and evaluation["addresses_question"] is True
    )

    sources = []

    if answered:
        for chunk in state["evidence"]:
            if chunk["chunk_id"] in draft.citation_ids:
                sources.append({
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "title": chunk["title"],
                    "content": chunk["content"],
                })

    trace = state["trace"] + ["finish"]

    response = {
        "question": state["question"],
        "status": "answered" if answered else "abstained",
        "answer": draft.answer if answered else ABSTENTION,
        "grounded": answered,
        "sources": sources,
        "reason": grounding.reason,
        "search_query": state["search_query"],
        "rewrite_count": state["rewrite_count"],
        "retrieval_attempts": state["retrieval_attempts"],
        "trace": trace,
        "intent": state["intent"],
        "route": state["route"],
        "evaluation": evaluation,
        "retrieval_degraded": state["retrieval_degraded"],
        "warnings": (
            [
                "Vector retrieval failed during this request. "
                "Keyword fallback was used, so retrieval coverage "
                "may be reduced."
            ]
            if state["retrieval_degraded"]
            else []
        ),
    }

    return {
        "response": response,
        "trace": trace,
    }
def analyze_node(state: RAGState):
    analysis = analyze_query(state["question"])

    return {
        "intent": analysis["intent"],
        "route": analysis["route"],
        "search_query": analysis["search_query"],
        "trace": state["trace"] + ["analyze"],
    }


def route_after_analysis(state: RAGState):
    return state["route"]


def direct_response_node(state: RAGState):
    trace = state["trace"] + ["direct_response"]

    response = {
        "question": state["question"],
        "status": "direct_answer",
        "answer": (
            "Hello! Ask me a question about the documents "
            "stored in this application."
        ),
        "grounded": False,
        "sources": [],
        "reason": (
            "A fixed greeting response; document grounding "
            "is not applicable."
        ),
        "intent": state["intent"],
        "route": state["route"],
        "search_query": state["search_query"],
        "rewrite_count": state["rewrite_count"],
        "retrieval_attempts": state["retrieval_attempts"],
        "trace": trace,

        "evaluation": {
        "evaluated": False,
        "addresses_question": None,
        "reason": "Not applicable to a fixed greeting.",
        },
        "retrieval_degraded": False,
        "warnings": [],
    }

    return {
        "response": response,
        "trace": trace,
    }

def evaluate_node(state: RAGState):
    # Do not spend another LLM call evaluating a rejected draft.
    if (
        not state["draft"].can_answer
        or not state["grounding"].supported
    ):
        evaluation = {
            "evaluated": False,
            "addresses_question": None,
            "reason": "Skipped because no grounded answer was available.",
        }

    else:
        result = evaluate_answer(
            question=state["question"],
            answer=state["draft"].answer,
        )

        evaluation = {
            "evaluated": True,
            "addresses_question": result.addresses_question,
            "reason": result.reason,
        }

    return {
        "evaluation": evaluation,
        "trace": state["trace"] + ["evaluate"],
    }

builder = StateGraph(RAGState)


#############
builder.add_node(
    "analyze",
    traced_node("analyze", analyze_node),
)

builder.add_node(
    "direct_response",
    traced_node("direct_response", direct_response_node),
)

builder.add_node(
    "retrieve",
    traced_node("retrieve", retrieve_node),
)

builder.add_node(
    "rerank",
    traced_node("rerank", rerank_node),
)

builder.add_node(
    "grade",
    traced_node("grade", grade_node),
)

builder.add_node(
    "rewrite",
    traced_node("rewrite", rewrite_node),
)

builder.add_node(
    "generate",
    traced_node("generate", generate_node),
)

builder.add_node(
    "grounding",
    traced_node("grounding", grounding_node),
)

builder.add_node(
    "evaluate",
    traced_node("evaluate", evaluate_node),
)

builder.add_node(
    "finish",
    traced_node("finish", finish_node),
)
#######

# Every request starts with query analysis.
builder.add_edge(START, "analyze")

# Route based on the analyzer's decision.
builder.add_conditional_edges(
    "analyze",
    route_after_analysis,
    {
        "direct": "direct_response",
        "retrieve": "retrieve",
    },
)

# Greetings finish without retrieval or LLM calls.
builder.add_edge("direct_response", END)

# Document questions follow the existing RAG pipeline.
builder.add_edge("retrieve", "rerank")
builder.add_edge("rerank", "grade")

builder.add_conditional_edges(
    "grade",
    route_after_grade,
    {
        "rewrite": "rewrite",
        "generate": "generate",
    },
)

builder.add_edge("rewrite", "retrieve")
builder.add_edge("generate", "grounding")
builder.add_edge("grounding", "evaluate")
builder.add_edge("evaluate", "finish")
builder.add_edge("finish", END)

rag_graph = builder.compile()


def run_rag(
    question,
    top_k=5,
    document_id=None,
    category=None,
    request_id=None,
):
    request_id = request_id or uuid4().hex
    started = perf_counter()

    result = rag_graph.invoke(
        {
            "question": question,
            "search_query": question,
            "top_k": top_k,
            "document_id": document_id,
            "category": category,
            "rewrite_count": 0,
            "retrieval_attempts": 0,
            "retrieval_degraded": False,
            "request_id": request_id,
            "trace": [],
        },
        config={"recursion_limit": 20},
    )

    response = result["response"]

    response["request_id"] = request_id
    response["latency_ms"] = round(
        (perf_counter() - started) * 1000,
        2,
    )

    log_event(
        "rag_finished",
        request_id,
        status=response["status"],
        latency_ms=response["latency_ms"],
        retrieval_attempts=response["retrieval_attempts"],
        rewrite_count=response["rewrite_count"],
        retrieval_degraded=response["retrieval_degraded"],
    )

    return response