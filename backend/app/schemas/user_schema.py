from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Username cannot be empty.")
        if len(value.strip()) < 3:
            raise ValueError("Username must be at least 3 characters long.")
        if any(ch.isspace() for ch in value):
            raise ValueError("Username cannot contain spaces.")
        return value.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if value.lower() == "password":
            raise ValueError("Password is too weak.")
        if not any(ch.isdigit() for ch in value):
            raise ValueError("Password must contain at least one digit.")
        if not any(ch.isalpha() for ch in value):
            raise ValueError("Password must contain at least one letter.")
        return value


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str
    department_id: int | None = None
    last_login_at: str | None = None

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    role: str | None = None
    department_id: int | None = None
    is_active: bool | None = None


class UserPasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)
    reason: str | None = Field(default="Administrative password reset")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
