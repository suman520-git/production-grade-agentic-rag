import logging

from openai import OpenAIError
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)

from backend.errors import RetrievalUnavailableError
from backend.keyword_search import search_keywords
from backend.retrieval import search_chunks


logger = logging.getLogger("rag.retrieval")


def search_hybrid(
    question,
    top_k=5,
    document_id=None,
    category=None,
):
    candidate_count = 10
    vector_failed = False

    try:
        vector_matches = search_chunks(
            question=question,
            top_k=candidate_count,
            document_id=document_id,
            category=category,
        )

    except (
        OpenAIError,
        ResponseHandlingException,
        UnexpectedResponse,
    ) as exc:
        vector_failed = True
        vector_matches = []

        logger.warning(
            "vector_retrieval_failed fallback=keyword type=%s",
            type(exc).__name__,
        )

    # PostgreSQL is still required for document filtering and keyword search.
    # A database failure propagates to the exception handler.
    keyword_matches = search_keywords(
        question=question,
        top_k=candidate_count,
        document_id=document_id,
        category=category,
    )

    if vector_failed and not keyword_matches:
        raise RetrievalUnavailableError(
            "Vector retrieval failed and keyword search found no candidates."
        )

    retrieval_mode = (
        "keyword_fallback"
        if vector_failed
        else "hybrid"
    )

    combined = {}

    rankings = [
        ("vector", vector_matches),
        ("keyword", keyword_matches),
    ]

    for method, matches in rankings:
        for rank, match in enumerate(matches, start=1):
            chunk_id = match["chunk_id"]

            if chunk_id not in combined:
                combined[chunk_id] = match.copy()
                combined[chunk_id].pop("score", None)

                combined[chunk_id]["rrf_score"] = 0.0
                combined[chunk_id]["vector_rank"] = None
                combined[chunk_id]["keyword_rank"] = None
                combined[chunk_id]["retrieval_mode"] = retrieval_mode

            combined[chunk_id][f"{method}_rank"] = rank
            combined[chunk_id]["rrf_score"] += 1 / (60 + rank)

    ranked_matches = sorted(
        combined.values(),
        key=lambda item: (
            -item["rrf_score"],
            item["chunk_id"],
        ),
    )

    return ranked_matches[:top_k]