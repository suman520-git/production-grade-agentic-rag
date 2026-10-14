from fastapi import FastAPI , HTTPException

from backend.config import settings
from backend.database import get_connection
from backend.schemas import DocumentCreate, SearchRequest
from backend.retrieval import search_chunks

from backend.keyword_search import search_keywords

from backend.hybrid_search import search_hybrid

from backend.reranker import rerank_chunks

from backend.grader import grade_chunks

from openai import OpenAIError
from langchain_core.exceptions import OutputParserException

from backend.generation import generate_answer, ABSTENTION
from backend.grounding import check_grounding
from backend.workflow import run_rag

from backend.uploads import router as uploads_router

from backend.document_store import save_document
from psycopg.rows import dict_row

from fastapi import Path
from backend.indexing import index_document


from backend.document_lifecycle import (
    delete_document,
    reindex_document,
)

from fastapi import Depends
from backend.security import require_api_key

from backend.rate_limiting import enforce_rate_limit
from fastapi.middleware.cors import CORSMiddleware
from backend.errors import register_error_handlers
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request
from backend.observability import log_event


from fastapi.responses import JSONResponse
from backend.readiness import check_readiness









app = FastAPI(
    title=settings.app_name,
    dependencies=[Depends(enforce_rate_limit)],
)

register_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
    expose_headers=["Retry-After", "X-Request-ID"],
    max_age=600,
)


@app.middleware("http")
async def trace_requests(request: Request, call_next):
    request_id = uuid4().hex
    request.state.request_id = request_id

    started = perf_counter()

    log_event(
        "request_started",
        request_id,
        method=request.method,
        path=request.url.path,
    )

    try:
        response = await call_next(request)

    except Exception as exc:
        log_event(
            "request_failed",
            request_id,
            level=logging.ERROR,
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_ms=round(
                (perf_counter() - started) * 1000,
                2,
            ),
            error_type=type(exc).__name__,
        )
        raise

    response.headers["X-Request-ID"] = request_id

    log_event(
        "request_finished",
        request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(
            (perf_counter() - started) * 1000,
            2,
        ),
    )

    return response






app.include_router(uploads_router)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env
    }


@app.get(
    "/ready",
    responses={
        503: {
            "description": "Required storage is unavailable or misconfigured."
        }
    },
)
def readiness(request: Request):
    result = check_readiness(
        request_id=request.state.request_id
    )

    status_code = (
        200
        if result["status"] == "ready"
        else 503
    )

    return JSONResponse(
        status_code=status_code,
        content=result,
    )





@app.post("/documents", status_code=201)
def create_document(document: DocumentCreate):
    return save_document(document)


@app.get("/documents")
def list_documents():
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute("""
                SELECT id, title, content, category, indexed, created_at
        FROM documents
        ORDER BY id;
            """)

            return cursor.fetchall()



@app.post("/search")
def search_documents(request: SearchRequest):

    matches = search_chunks(
        question=request.question,
        top_k=request.top_k,
        document_id=request.document_id,
        category=request.category,
    )

    return {
        "question": request.question,
        "matches_found": len(matches),
        "matches": matches
    }



@app.post("/search/keyword")
def keyword_search_documents(request: SearchRequest):

    matches = search_keywords(
        question=request.question,
        top_k=request.top_k,
        document_id=request.document_id,
        category=request.category,
    )

    return {
        "question": request.question,
        "matches_found": len(matches),
        "matches": matches
    }


@app.post("/search/hybrid")
def hybrid_search_documents(request: SearchRequest):

    matches = search_hybrid(
        question=request.question,
        top_k=request.top_k,
        document_id=request.document_id,
        category=request.category,
    )

    return {
        "question": request.question,
        "matches_found": len(matches),
        "matches": matches
    }


@app.post("/search/reranked")
def reranked_search_documents(request: SearchRequest):

    candidates = search_hybrid(
        question=request.question,
        top_k=10,
        document_id=request.document_id,
        category=request.category,
    )

    ranked = rerank_chunks(request.question, candidates)

    matches = ranked[:request.top_k]

    return {
        "question": request.question,
        "matches_found": len(matches),
        "matches": matches
    }


@app.post("/search/graded")
def graded_search_documents(request: SearchRequest):

    candidates = search_hybrid(
        question=request.question,
        top_k=10,
        document_id=request.document_id,
        category=request.category,
    )

    ranked = rerank_chunks(request.question, candidates)

    graded = grade_chunks(request.question, ranked)

    matches = graded["relevant_chunks"][:request.top_k]

    return {
        "question": request.question,
        "candidates_found": len(candidates),
        "relevant_found": len(graded["relevant_chunks"]),
        "matches_found": len(matches),
        "matches": matches,
        "rejected_chunks": graded["rejected_chunks"],
        "reason": graded["reason"]
    }


@app.post("/chat")
def chat(request: SearchRequest, http_request: Request):
    try:
        return run_rag(
            question=request.question,
            top_k=request.top_k,
            document_id=request.document_id,
            category=request.category,
            request_id=http_request.state.request_id,
        )

    except (OpenAIError, OutputParserException, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="The AI processing step failed. Please try again later.",
        ) from exc



@app.post("/documents/{document_id}/index")
def index_saved_document(
    document_id: int = Path(..., gt=0, le=2147483647),
):
    return index_document(document_id)    



@app.post("/documents/{document_id}/reindex")
def reindex_saved_document(
    document_id: int = Path(..., gt=0, le=2147483647),
):
    return reindex_document(document_id)


@app.delete("/documents/{document_id}")
def delete_saved_document(
    document_id: int = Path(..., gt=0, le=2147483647),
):
    return delete_document(document_id)


