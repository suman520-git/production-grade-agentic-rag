from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from backend.document_store import save_document
from backend.schemas import Category, DocumentCreate


router = APIRouter(tags=["Documents"])

MAX_UPLOAD_BYTES = 1_000_000


@router.post("/documents/upload", status_code=201)
def upload_document(
    title: str = Form(...),
    category: Category = Form("general"),
    file: UploadFile = File(...),
):
    try:
        filename = file.filename or ""

        if not filename.lower().endswith(".txt"):
            raise HTTPException(
                status_code=415,
                detail="Only UTF-8 .txt files are supported.",
            )

        raw_content = file.file.read(MAX_UPLOAD_BYTES + 1)

        if len(raw_content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="The file must not exceed 1,000,000 bytes.",
            )

        try:
            content = raw_content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail="Save the text file using UTF-8 encoding.",
            ) from exc

        try:
            document = DocumentCreate(
                title=title,
                content=content,
                category=category,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=exc.errors(
                    include_context=False,
                    include_input=False,
                    include_url=False,
                ),
            ) from exc

        return save_document(document)

    finally:
        file.file.close()