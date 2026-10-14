from importlib.metadata import version
from pathlib import Path


packages = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "pydantic-settings",
    "psycopg",
    "psycopg-binary",
    "langchain-core",
    "langchain-openai",
    "langchain-text-splitters",
    "langgraph",
    "openai",
    "qdrant-client",
    "python-multipart",
    "limits",
    "streamlit",
    "httpx",
]

requirements = [
    f"{package}=={version(package)}"
    for package in packages
]

path = Path(__file__).resolve().parent / "requirements.txt"
path.write_text(
    "\n".join(requirements) + "\n",
    encoding="utf-8",
)

print(path.read_text(encoding="utf-8"))
print(f"Saved: {path}")