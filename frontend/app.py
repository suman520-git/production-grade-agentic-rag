from pathlib import Path

import httpx
import streamlit as st
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class FrontendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_base_url: str = "http://127.0.0.1:8000"


settings = FrontendSettings()

API_BASE_URL = settings.api_base_url.rstrip("/")
MAX_UPLOAD_BYTES = 1_000_000

st.set_page_config(
    page_title="Agentic RAG",
    page_icon="📚",
    layout="wide",
)

st.title("Agentic RAG")
st.caption("Upload documents and view the knowledge available to your assistant.")
def clear_chat():
    st.session_state["chat_messages"] = []



with st.sidebar:
    st.header("Access")

    api_key = st.text_input(
        "Application API key",
        type="password",
        key="application_api_key",
        help="Enter your APP_API_KEY, not your OpenAI key.",
        on_change=clear_chat,
    )

    st.caption("Your key is used to authenticate requests to the backend.")

if not api_key:
    st.info("Enter your application API key in the sidebar to continue.")
    st.stop()


def call_api(method, path, **kwargs):
    try:
        # Uploading also performs embeddings, so allow time for processing.
        # This is a network inactivity timeout, not a total job deadline.
        timeout = httpx.Timeout(180.0, connect=5.0)

        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = client.request(
                method,
                f"{API_BASE_URL}{path}",
                headers={"X-API-Key": api_key},
                **kwargs,
            )

    except httpx.TimeoutException:
        st.error(
            "The request timed out. If you submitted a document, "
            "refresh the document list before uploading it again. "
            "The backend may still be processing it."
        )
        return None

    except httpx.RequestError:
        st.error(
            "Cannot reach the backend. Check that FastAPI is running."
        )
        return None

    try:
        payload = response.json()
    except ValueError:
        st.error(
            f"The backend returned an unexpected response "
            f"(HTTP {response.status_code})."
        )
        return None

    if response.is_success:
        return payload

    if response.status_code == 401:
        st.error("Your application API key is missing or incorrect.")

    elif response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "a few")
        st.warning(
            f"Too many requests. Try again after {retry_after} seconds."
        )

    elif response.status_code == 409:
        st.warning(
            "The document already exists in this category, "
            "or it is currently being processed."
        )

    else:
        st.error(f"The request failed (HTTP {response.status_code}).")

    detail = payload.get("detail") if isinstance(payload, dict) else payload

    if detail is not None:
        with st.expander("Error details"):
            if isinstance(detail, str):
                st.text(detail)
            else:
                st.json(detail)

    return None


st.subheader("Upload a document")

with st.form("document_upload_form", clear_on_submit=False):
    title = st.text_input(
        "Document title",
        max_chars=200,
    )

    category = st.selectbox(
        "Category",
        options=["general", "hr", "it", "finance"],
    )

    uploaded_file = st.file_uploader(
        "Choose a UTF-8 text file",
        type=["txt"],
        accept_multiple_files=False,
    )

    st.caption(
        "Maximum file size: 1,000,000 bytes. "
        "Document text must contain 20–200,000 characters."
    )

    submitted = st.form_submit_button("Upload and index")

if submitted:
    if not title.strip():
        st.error("Enter a document title.")

    elif uploaded_file is None:
        st.error("Choose a text file.")

    elif uploaded_file.size > MAX_UPLOAD_BYTES:
        st.error("The file must not exceed 1,000,000 bytes.")

    else:
        with st.spinner("Saving and indexing your document..."):
            result = call_api(
                "POST",
                "/documents/upload",
                data={
                    "title": title.strip(),
                    "category": category,
                },
                files={
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        "text/plain",
                    )
                },
            )

        if result is not None:
            st.success(
                f"Document {result['id']} saved and indexed "
                f"into {result['chunks_indexed']} chunk(s)."
            )


st.divider()
st.subheader("Saved documents")

# Clicking this button reruns the page and fetches a fresh list.
st.button("Refresh documents")

documents = call_api("GET", "/documents")

if documents is None:
    st.stop()

if not documents:
    st.info("No documents have been saved yet.")
    st.stop()

table_rows = [
    {
        "ID": document["id"],
        "Title": document["title"],
        "Category": document["category"],
        "Searchable": "Yes" if document["indexed"] else "No",
        "Created": document["created_at"],
    }
    for document in documents
]

st.dataframe(
    table_rows,
    hide_index=True,
    use_container_width=True,
)

documents_by_id = {
    document["id"]: document
    for document in documents
}

selected_id = st.selectbox(
    "View a document",
    options=list(documents_by_id),
    format_func=lambda document_id: (
        f"{document_id} — {documents_by_id[document_id]['title']}"
    ),
)

selected_document = documents_by_id[selected_id]

if not selected_document["indexed"]:
    st.warning(
        "This document is saved but is not currently searchable. "
        "Use its indexing endpoint in Swagger to index it."
    )

with st.expander("Document content", expanded=True):
    st.text(selected_document["content"])



st.divider()
st.subheader("Ask your documents")

st.caption(
    "Ask a complete question each time. "
    "Previous messages are displayed but are not sent to the model."
)

if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []


def display_answer(result):
    if result["status"] == "abstained":
        st.warning(
            "The documents did not provide enough verified information."
        )

    elif result["status"] == "direct_answer":
        st.caption("Direct response")

    else:
        st.caption("Document-based answer")

    st.text(result["answer"])

    for warning in result.get("warnings", []):
        st.warning(warning)

    for source in result.get("sources", []):
        label = (
            f"Source [{source['chunk_id']}] "
            f"— Document {source['document_id']}"
        )

        with st.expander(label):
            st.text(source["title"])
            st.text(source["content"])


category_column, document_column = st.columns(2)

with category_column:
    chat_category = st.selectbox(
        "Search category",
        options=["All categories", "general", "hr", "it", "finance"],
        key="chat_category",
    )

category_filter = (
    None
    if chat_category == "All categories"
    else chat_category
)

# Include only indexed documents matching the selected category.
searchable_documents = {
    document["id"]: document
    for document in documents
    if document["indexed"]
    and (
        category_filter is None
        or document["category"] == category_filter
    )
}

document_options = [None] + list(searchable_documents)

# Reset the selected document if it no longer matches the category.
if st.session_state.get("chat_document_id") not in document_options:
    st.session_state["chat_document_id"] = None

with document_column:
    chat_document_id = st.selectbox(
        "Search document",
        options=document_options,
        format_func=lambda document_id: (
            "All documents in selected category"
            if document_id is None
            else (
                f"{document_id} — "
                f"{searchable_documents[document_id]['title']}"
            )
        ),
        key="chat_document_id",
    )

if not searchable_documents:
    st.info("There are no searchable documents in this category.")

if st.button("Clear chat"):
    clear_chat()

# Redisplay previous exchanges without calling the backend again.
for message in st.session_state["chat_messages"]:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.text(message["content"])
            st.caption(message["scope"])
        else:
            display_answer(message["result"])

question = st.chat_input(
    "Ask a question about your documents",
    max_chars=2000,
)

if question:
    question = question.strip()

    if len(question) < 3:
        st.error("Enter a question with at least three characters.")

    else:
        scope = (
            f"Category: {chat_category} | "
            f"Document: {chat_document_id or 'All matching documents'}"
        )

        with st.chat_message("user"):
            st.text(question)
            st.caption(scope)

        with st.chat_message("assistant"):
            with st.spinner("Searching documents and checking the answer..."):
                result = call_api(
                    "POST",
                    "/chat",
                    json={
                        "question": question,
                        "top_k": 5,
                        "document_id": chat_document_id,
                        "category": category_filter,
                    },
                )

            if result is not None:
                display_answer(result)

        if result is not None:
            st.session_state["chat_messages"].extend([
                {
                    "role": "user",
                    "content": question,
                    "scope": scope,
                },
                {
                    "role": "assistant",
                    "result": result,
                },
            ])

            # Keep the latest ten question/answer pairs.
            st.session_state["chat_messages"] = (
                st.session_state["chat_messages"][-20:]
            )
