from langchain_openai import OpenAIEmbeddings

from backend.config import settings


# Configure the client that will request embeddings from OpenAI.
embedding_model = OpenAIEmbeddings(
    model=settings.embedding_model,
    dimensions=settings.embedding_dimensions,
    api_key=settings.openai_api_key.get_secret_value(),
    request_timeout=30,
    max_retries=2
)

