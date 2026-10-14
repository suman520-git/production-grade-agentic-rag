from contextlib import contextmanager

import psycopg
from fastapi import HTTPException

from backend.database import get_connection


@contextmanager
def document_lock(document_id):
    connection = None

    try:
        connection = get_connection()
        connection.autocommit = True

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_lock(%s, %s);",
                (8108, document_id),
            )

            acquired = cursor.fetchone()[0]

        if not acquired:
            raise HTTPException(
                status_code=409,
                detail="This document is being processed. Try again later.",
            )

        yield

    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="Document processing is unavailable. Please try again later.",
        ) from exc

    finally:
        if connection is not None:
            # Closing the session releases its advisory lock.
            connection.close()