import logging

import psycopg
from fastapi import Request
from fastapi.responses import JSONResponse
from langchain_core.exceptions import OutputParserException
from openai import OpenAIError
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)

from backend.config import settings


logger = logging.getLogger("rag.errors")


class RetrievalUnavailableError(RuntimeError):
    pass


async def dependency_error_handler(request: Request, exc: Exception):
    # Avoid logging API keys, document text, or raw provider responses.
    logger.error(
        "dependency_failure method=%s path=%s type=%s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )

    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "A required service is unavailable. "
                "Please try again later."
            )
        },
    )


async def unexpected_error_handler(request: Request, exc: Exception):
    logger.error(
        "unexpected_failure method=%s path=%s type=%s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )

    # Unhandled-error responses can be created outside CORS middleware.
    headers = {
    "X-Request-ID": getattr(request.state, "request_id", "unknown"),
}

    origin = request.headers.get("origin")

    if origin in settings.cors_origins:
        headers.update({
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Expose-Headers": "X-Request-ID",
            "Vary": "Origin",
        })

    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected server error occurred."
        },
        headers=headers,
    )


def register_error_handlers(app):
    dependency_errors = (
        psycopg.OperationalError,
        psycopg.InterfaceError,
        OpenAIError,
        OutputParserException,
        ResponseHandlingException,
        UnexpectedResponse,
        RetrievalUnavailableError,
    )

    for error_type in dependency_errors:
        app.add_exception_handler(
            error_type,
            dependency_error_handler,
        )

    app.add_exception_handler(
        Exception,
        unexpected_error_handler,
    )