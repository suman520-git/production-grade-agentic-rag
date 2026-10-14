import psycopg

from fastapi import HTTPException
from openai import OpenAIError
from psycopg.rows import dict_row
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
    PointStruct,
)

from backend.chunking import create_chunks
from backend.config import settings
from backend.database import get_connection
from backend.embeddings import embedding_model
from backend.document_lock import document_lock

def _index_document(document_id):
    try:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                # Prevent simultaneous indexing of the same document.
                cursor.execute(
                    """
                    SELECT id, title, content, category, indexed
                    FROM documents
                    WHERE id = %s
                    FOR UPDATE NOWAIT;
                    """,
                    (document_id,),
                )

                document = cursor.fetchone()

                if document is None:
                    raise HTTPException(
                        status_code=404,
                        detail="Document not found.",
                    )

                # Repeated calls do not regenerate a completed index.
                if document["indexed"]:
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS count
                        FROM document_chunks
                        WHERE document_id = %s;
                        """,
                        (document_id,),
                    )

                    return {
                        "document_id": document_id,
                        "indexed": True,
                        "chunks_indexed": cursor.fetchone()["count"],
                        "already_indexed": True,
                    }

                chunks = create_chunks(document["content"])

                if not chunks:
                    raise ValueError("No usable chunks were produced.")

                vectors = embedding_model.embed_documents(
                    [chunk["content"] for chunk in chunks]
                )

                if len(vectors) != len(chunks):
                    raise ValueError("Embedding count does not match chunks.")

                points = []

                for chunk, vector in zip(chunks, vectors):
                    if len(vector) != settings.embedding_dimensions:
                        raise ValueError("Unexpected embedding dimensions.")

                    cursor.execute(
                        """
                        INSERT INTO document_chunks (
                            document_id,
                            chunk_index,
                            content,
                            start_char
                        )
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (document_id, chunk_index)
                        DO UPDATE SET
                            content = EXCLUDED.content,
                            start_char = EXCLUDED.start_char
                        RETURNING id;
                        """,
                        (
                            document_id,
                            chunk["chunk_index"],
                            chunk["content"],
                            chunk["start_char"],
                        ),
                    )

                    chunk_id = cursor.fetchone()["id"]

                    points.append(
                        PointStruct(
                            id=chunk_id,
                            vector=vector,
                            payload={
                                "document_id": document_id,
                                "chunk_index": chunk["chunk_index"],
                                "title": document["title"],
                                "content": chunk["content"],
                                "category": document["category"],
                                "start_char": chunk["start_char"],
                            },
                        )
                    )

                cursor.execute(
                    """
                    DELETE FROM document_chunks
                    WHERE document_id = %s
                      AND chunk_index >= %s;
                    """,
                    (document_id, len(chunks)),
                )

                client = QdrantClient(
                    url=settings.qdrant_url,
                    timeout=30,
                )

                try:
                    # Remove leftovers from any failed earlier attempt.
                    # This document is still excluded from retrieval.
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

                    client.upsert(
                        collection_name=settings.qdrant_collection,
                        points=points,
                        wait=True,
                    )

                finally:
                    client.close()

                # Search becomes available only after vector storage succeeds.
                cursor.execute(
                    """
                    UPDATE documents
                    SET indexed = TRUE
                    WHERE id = %s;
                    """,
                    (document_id,),
                )

        return {
            "document_id": document_id,
            "indexed": True,
            "chunks_indexed": len(chunks),
            "already_indexed": False,
        }

    except psycopg.errors.LockNotAvailable as exc:
        raise HTTPException(
            status_code=409,
            detail="This document is currently being processed. Try again later.",
        ) from exc

    except (
        OpenAIError,
        UnexpectedResponse,
        ResponseHandlingException,
        psycopg.Error,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "message": (
                    "Indexing could not be confirmed. "
                    "Check GET /documents and retry the indexing endpoint."
                ),
                "document_id": document_id,
                "retry_endpoint": f"/documents/{document_id}/index",
            },
        ) from exc



def index_document(document_id):
    with document_lock(document_id):
        return _index_document(document_id)
    