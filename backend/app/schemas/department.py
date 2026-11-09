from pydantic import BaseModel, Field


class DepartmentCreateRequest(BaseModel):
    department_name: str = Field(..., min_length=3, max_length=255)
    department_type: str = Field(..., min_length=2, max_length=100)
    department_code: str | None = Field(None, max_length=50)
    jurisdiction: str | None = Field(None, max_length=150)
    location: str | None = Field(None, max_length=255)
    latitude: float | None = None
    longitude: float | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notification_enabled: bool = True
    is_central: bool = False


class DepartmentUpdateRequest(BaseModel):
    department_name: str | None = Field(None, min_length=3, max_length=255)
    department_type: str | None = Field(None, min_length=2, max_length=100)
    department_code: str | None = Field(None, max_length=50)
    jurisdiction: str | None = Field(None, max_length=150)
    location: str | None = Field(None, max_length=255)
    latitude: float | None = None
    longitude: float | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notification_enabled: bool | None = None
    is_central: bool | None = None


class DepartmentStatusUpdate(BaseModel):
    is_active: bool


class DepartmentResponse(BaseModel):
    id: int
    department_name: str
    department_type: str
    department_code: str | None = None
    jurisdiction: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notification_enabled: bool = True
    is_central: bool = False
    is_active: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
