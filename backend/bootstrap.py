import time

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)
from qdrant_client.models import Distance, VectorParams

from backend.config import settings
from backend.database import get_connection


def prepare_database():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    content TEXT NOT NULL,
                    category VARCHAR(20) NOT NULL DEFAULT 'general',
                    content_hash VARCHAR(64) NOT NULL,
                    indexed BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    documents_category_content_hash_key
                ON documents (category, content_hash)
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    document_id INTEGER NOT NULL
                        REFERENCES documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL
                        CHECK (chunk_index >= 0),
                    content TEXT NOT NULL,
                    start_char INTEGER,
                    created_at TIMESTAMPTZ NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (document_id, chunk_index)
                )
            """)

            # Verify the columns required by this application.
            cursor.execute("""
                SELECT
                    id, title, content, category,
                    content_hash, indexed, created_at
                FROM documents
                LIMIT 0
            """)

            cursor.execute("""
                SELECT
                    id, document_id, chunk_index,
                    content, start_char, created_at
                FROM document_chunks
                LIMIT 0
            """)

            cursor.execute("""
                SELECT COUNT(*)
                FROM documents
                WHERE indexed = TRUE
            """)

            indexed_documents = cursor.fetchone()[0]

    print("PostgreSQL schema is ready.", flush=True)
    return indexed_documents


def prepare_qdrant(indexed_documents):
    client = QdrantClient(
        url=settings.qdrant_url,
        timeout=3,
    )

    try:
        # A started container may still be initializing.
        for attempt in range(1, 16):
            try:
                client.get_collections()
                break

            except (
                ResponseHandlingException,
                UnexpectedResponse,
            ) as exc:
                if attempt == 15:
                    raise RuntimeError(
                        "Qdrant was not available after 15 attempts."
                    ) from exc

                print(
                    f"Waiting for Qdrant: attempt {attempt}/15",
                    flush=True,
                )
                time.sleep(2)

        exists = client.collection_exists(
            collection_name=settings.qdrant_collection
        )

        if not exists:
            if indexed_documents:
                raise RuntimeError(
                    "PostgreSQL contains indexed documents, but the "
                    "Qdrant collection is missing. Check the Qdrant "
                    "volume and collection setting before continuing."
                )

            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dimensions,
                    distance=Distance.COSINE,
                ),
            )

            print("Created the Qdrant collection.", flush=True)

        collection = client.get_collection(
            collection_name=settings.qdrant_collection
        )

        vectors = collection.config.params.vectors

        if (
            not isinstance(vectors, VectorParams)
            or vectors.size != settings.embedding_dimensions
            or vectors.distance != Distance.COSINE
        ):
            raise RuntimeError(
                "The existing Qdrant vector configuration does not "
                "match the application settings."
            )

        print("Qdrant collection is ready.", flush=True)

    finally:
        client.close()


def main():
    indexed_documents = prepare_database()
    prepare_qdrant(indexed_documents)
    print("Application initialization completed.", flush=True)


if __name__ == "__main__":
    main()