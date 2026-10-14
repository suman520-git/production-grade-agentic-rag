from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from backend.config import settings
from backend.embeddings import embedding_model

from qdrant_client.models import MatchAny
from backend.document_filters import resolve_document_ids


def search_chunks( question,
    top_k=5,
    document_id=None,
    category=None,):

    

   
    allowed_ids = resolve_document_ids(
        document_id=document_id,
        category=category,
    )

    if allowed_ids == []:
        return []

    query_filter = None

    if allowed_ids is not None:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchAny(any=allowed_ids),
                )
            ]
        )

    query_vector = embedding_model.embed_query(question)

    client = QdrantClient(
        url=settings.qdrant_url,
        timeout=30
    )

    try:
        result = client.query_points(
            collection_name=settings.qdrant_collection,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True
        )

        matches = []

        for point in result.points:
            payload = point.payload or {}

            matches.append({
                "chunk_id": point.id,
                "document_id": payload.get("document_id"),
                "chunk_index": payload.get("chunk_index"),
                "title": payload.get("title"),
                "content": payload.get("content"),
                "score": point.score
            })

        return matches

    finally:
        # Close the client even if the search raises an error.
        client.close()