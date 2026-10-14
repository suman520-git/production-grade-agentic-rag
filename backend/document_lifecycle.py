import psycopg

from fastapi import HTTPException
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)
from qdrant_client.models import (
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
)

from backend.config import settings
from backend.database import get_connection
from backend.document_lock import document_lock
from backend.indexing import _index_document


def mark_not_searchable(document_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE documents
                SET indexed = FALSE
                WHERE id = %s
                RETURNING id;
                """,
                (document_id,),
            )

            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=404,
                    detail="Document not found.",
                )


def reindex_document(document_id):
    with document_lock(document_id):
        # Commit this change before replacing any vectors.
        mark_not_searchable(document_id)

        result = _index_document(document_id)

        return {
            **result,
            "message": "Document reindexed successfully",
        }


def delete_document(document_id):
    with document_lock(document_id):
        # If removal fails, new searches must exclude this document.
        mark_not_searchable(document_id)

        try:
            client = QdrantClient(
                url=settings.qdrant_url,
                timeout=30,
            )

            try:
                client.delete(
                    collection_name=settings.qdrant_collection,
                    points_selector=FilterSelector(
                        filter=Filter(
                            must=[
                                FieldCondition(
                                    key="document_id",
                                    match=MatchValue(value=document_id),
                                )
                            ]
                        )
                    ),
                    wait=True,
                )
            finally:
                client.close()

            # document_chunks has ON DELETE CASCADE.
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM documents WHERE id = %s;",
                        (document_id,),
                    )

        except (
            UnexpectedResponse,
            ResponseHandlingException,
            psycopg.Error,
        ) as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "message": (
                        "Deletion could not be confirmed. "
                        "Check document storage and retry deletion."
                    ),
                    "document_id": document_id,
                },
            ) from exc

    return {
        "document_id": document_id,
        "deleted": True,
    }