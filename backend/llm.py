from langchain_openai import ChatOpenAI

from backend.config import settings


llm = ChatOpenAI(
    model=settings.openai_model,
    api_key=settings.openai_api_key.get_secret_value(),
    temperature=0,
    timeout=30,
    max_retries=2
)

