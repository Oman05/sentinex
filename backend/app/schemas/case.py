from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.models.case import CaseCategory, CasePriority, CaseStatus


class CaseCreateRequest(BaseModel):
    category: CaseCategory
    title: str = Field(..., min_length=3, max_length=255)
    person_identifier: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=10, max_length=2000)
    department_id: int | None = None
    priority: CasePriority = CasePriority.MEDIUM
    last_known_location: str | None = Field(default=None, min_length=2, max_length=255)
    status: CaseStatus | None = None

    @field_validator("title", "person_identifier", "description", "last_known_location")
    @classmethod
    def strip_fields(cls, value):
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field cannot be blank")
        return stripped


class CaseUpdateRequest(BaseModel):
    category: CaseCategory | None = None
    title: str | None = Field(default=None, min_length=3, max_length=255)
    person_identifier: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, min_length=10, max_length=2000)
    department_id: int | None = None
    priority: CasePriority | None = None
    last_known_location: str | None = Field(default=None, min_length=2, max_length=255)

    @field_validator("title", "person_identifier", "description", "last_known_location")
    @classmethod
    def strip_fields(cls, value):
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field cannot be blank")
        return stripped


class CaseStatusUpdateRequest(BaseModel):
    status: CaseStatus


class CaseSummaryResponse(BaseModel):
    id: int
    case_number: str
    category: str
    title: str
    person_identifier: str
    department_id: int
    created_by: int
    status: str
    priority: str
    last_known_location: str | None = None
    is_active: bool
    created_at: str
    updated_at: str
    closed_at: str | None = None

    model_config = {"from_attributes": True}


class CaseDetailResponse(CaseSummaryResponse):
    description: str


class PaginatedCasesResponse(BaseModel):
    items: list[CaseSummaryResponse]
    total: int
    page: int
    size: int


class CaseDeleteResponse(BaseModel):
    message: str
    case_id: int
