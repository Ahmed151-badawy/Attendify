"""app/schemas/chat.py — Chat API payload schemas."""
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Session ID from /chat/init")
    message: str = Field(..., min_length=1, max_length=4000, description="User message text.")
    course_context: str | None = Field(None, description="Optional course ID hint.")

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, v: str) -> str:
        """Strip leading/trailing whitespace before length validation."""
        if isinstance(v, str):
            return v.strip()
        return v


class ChatInitResponse(BaseModel):
    session_id: str
    user_id: str
    role: str
    capabilities: list[str]
    system_prompt_preview: str


class TokenRequest(BaseModel):
    email: str
    roles: list[str] = ["student"]
    faculty_id: int | None = None
    institution_id: str = "inst-00000000-0000-4000-8000-000000000001"

    @field_validator("roles", mode="before")
    @classmethod
    def ensure_non_empty_roles(cls, v: list) -> list:
        """Ensure at least one role is specified."""
        if not v:
            return ["student"]
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
