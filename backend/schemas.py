from pydantic import BaseModel, ConfigDict, Field

from typing import Literal

from pydantic import field_validator

Category = Literal["general", "hr", "it", "finance"]


# Rules for document data received by the API.
class DocumentCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=20, max_length=200000)
    category: Category = "general"

    @field_validator("title", "content")
    @classmethod
    def reject_null_characters(cls, value):
        if "\x00" in value:
            raise ValueError("Text must not contain null characters.")
        return value


class SearchRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )

    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)
    document_id: int | None = Field(default=None, gt=0)

    category: Category | None = None


class RerankResult(BaseModel):
    chunk_ids: list[int] = Field(
        description="Every supplied chunk ID, ordered from most to least useful."
    )


class GradeResult(BaseModel):
    relevant_chunk_ids: list[int] = Field(
        description="IDs of supplied chunks that contain relevant evidence."
    )

    reason: str = Field(
        description="Brief explanation of the relevance decisions."
    )


class AnswerResult(BaseModel):
    can_answer: bool
    answer: str
    citation_ids: list[int]


class GroundingResult(BaseModel):
    supported: bool
    reason: str


class RewriteResult(BaseModel):
    search_query: str = Field(
        description=(
            "A concise search query preserving the original question's "
            "meaning, entities, numbers and constraints."
        )
    )

class AnswerEvaluationResult(BaseModel):
    addresses_question: bool
    reason: str


    

