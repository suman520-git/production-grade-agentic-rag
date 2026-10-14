import re

from psycopg.rows import dict_row

from backend.database import get_connection
from backend.document_filters import resolve_document_ids


def search_keywords(
    question,
    top_k=5,
    document_id=None,
    category=None,
):
    allowed_ids = resolve_document_ids(
        document_id=document_id,
        category=category,
    )

    if allowed_ids == []:
        return []

    words = re.findall(r"[a-zA-Z0-9]+", question)

    if not words:
        return []

    keyword_query = " OR ".join(words)

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    c.chunk_index,
                    d.title,
                    c.content,
                    ts_rank_cd(
                        to_tsvector('english', c.content),
                        websearch_to_tsquery('english', %s)
                    ) AS score
                FROM document_chunks AS c
                JOIN documents AS d ON d.id = c.document_id
                WHERE
                    to_tsvector('english', c.content)
                    @@ websearch_to_tsquery('english', %s)
                    AND (
                        %s::integer[] IS NULL
                        OR c.document_id = ANY(%s::integer[])
                    )
                ORDER BY score DESC, c.id
                LIMIT %s;
                """,
                (
                    keyword_query,
                    keyword_query,
                    allowed_ids,
                    allowed_ids,
                    top_k,
                ),
            )

            return cursor.fetchall()