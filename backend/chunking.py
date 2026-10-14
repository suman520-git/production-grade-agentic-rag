from langchain_text_splitters import RecursiveCharacterTextSplitter


splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=100,
    length_function=len,
    add_start_index=True,
)


def create_chunks(content):
    documents = splitter.create_documents([content])

    chunks = []

    for index, document in enumerate(documents):
        if not document.page_content.strip():
            continue

        chunks.append({
            "chunk_index": index,
            "content": document.page_content,
            "start_char": document.metadata["start_index"],
        })

    return chunks