import logging

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)
from qdrant_client.models import Distance, VectorParams

from backend.config import settings
from backend.database import get_connection
from backend.observability import log_event


def check_postgres(request_id: str) -> str:
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET LOCAL statement_timeout = '2s'"
                )
                cursor.execute(
                    "SET LOCAL lock_timeout = '1s'"
                )

                # Check that the expected tables and columns exist.
                # LIMIT 0 avoids reading document content.
                cursor.execute("""
                    SELECT
                        id,
                        title,
                        content,
                        category,
                        content_hash,
                        indexed,
                        created_at
                    FROM public.documents
                    LIMIT 0
                """)

                cursor.execute("""
                    SELECT
                        id,
                        document_id,
                        chunk_index,
                        content,
                        start_char,
                        created_at
                    FROM public.document_chunks
                    LIMIT 0
                """)

        return "ready"

    except psycopg.Error as exc:
        log_event(
            "readiness_check_failed",
            request_id,
            level=logging.WARNING,
            service="postgres",
            error_type=type(exc).__name__,
        )
        return "unavailable"


def check_qdrant(request_id: str) -> str:
    client = QdrantClient(
        url=settings.qdrant_url,
        timeout=3,
    )

    try:
        collection = client.get_collection(
            collection_name=settings.qdrant_collection
        )

        vectors = collection.config.params.vectors

        # Our application uses one unnamed vector per chunk.
        configuration_matches = (
            isinstance(vectors, VectorParams)
            and vectors.size == settings.embedding_dimensions
            and vectors.distance == Distance.COSINE
        )

        if not configuration_matches:
            log_event(
                "readiness_check_failed",
                request_id,
                level=logging.WARNING,
                service="qdrant",
                reason="vector_configuration_mismatch",
            )
            return "configuration_mismatch"

        return "ready"

    except (ResponseHandlingException, UnexpectedResponse) as exc:
        log_event(
            "readiness_check_failed",
            request_id,
            level=logging.WARNING,
            service="qdrant",
            error_type=type(exc).__name__,
        )
        return "unavailable"

    finally:
        client.close()


def check_readiness(request_id: str) -> dict:
    checks = {
        "postgres": check_postgres(request_id),
        "qdrant": check_qdrant(request_id),
    }

    ready = all(
        result == "ready"
        for result in checks.values()
    )

    return {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
        "openai": "not_checked",
        "request_id": request_id,
    }