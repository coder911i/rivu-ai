"""Pydantic schemas for authentication."""
from typing import Any
from pydantic import BaseModel, EmailStr, field_validator, model_validator
import re


class SignupRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(v) > 50:
            raise ValueError("Username must be at most 50 characters")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username may only contain letters, numbers, underscores, and hyphens")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain a lowercase letter")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain an uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain a number")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email address")
        return v


class EmailTokenRequest(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetCompleteRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        if not any(c.islower() for c in v) or not any(c.isupper() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain uppercase, lowercase, and numeric characters")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str | None
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class GoogleAuthRequest(BaseModel):
    id_token: str | None = None
    credential: str | None = None

    @field_validator("id_token", mode="before")
    @classmethod
    def validate_id_token(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
        return v or None

    @field_validator("credential", mode="before")
    @classmethod
    def validate_credential(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
        return v or None

    @model_validator(mode="after")
    def check_token_present(self) -> "GoogleAuthRequest":
        token = self.id_token or self.credential
        if not token:
            raise ValueError("Google ID token is required")
        self.id_token = token
        return self
