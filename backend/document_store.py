import hashlib

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row

from backend.database import get_connection
from backend.schemas import DocumentCreate
from backend.indexing import index_document

def save_document(document: DocumentCreate):
    content_hash = hashlib.sha256(
        document.content.encode("utf-8")
    ).hexdigest()

    try:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    INSERT INTO documents (
                        title,
                        content,
                        category,
                        content_hash
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (category, content_hash)
                    DO NOTHING
                    RETURNING id, title, category, created_at;
                    """,
                    (
                        document.title,
                        document.content,
                        document.category,
                        content_hash,
                    ),
                )

                row = cursor.fetchone()

    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="Document storage is unavailable. Please try again later.",
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=409,
            detail="This document content already exists in this category.",
        )

    # The document insert has committed before indexing begins.
    indexing_result = index_document(row["id"])
    
    
    return {
        "message": "Document saved and indexed successfully",
        **row,
        "saved": True,
        "indexed": indexing_result["indexed"],
        "chunks_indexed": indexing_result["chunks_indexed"],
    }