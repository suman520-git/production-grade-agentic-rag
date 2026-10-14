from backend.database import get_connection


def resolve_document_ids(document_id=None, category=None):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM documents
                WHERE indexed = TRUE
                  AND (%s::integer IS NULL OR id = %s)
                  AND (%s::text IS NULL OR category = %s)
                ORDER BY id;
                """,
                (document_id, document_id, category, category),
            )

            return [row[0] for row in cursor.fetchall()]