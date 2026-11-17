"""
app/core/security.py  —  Phase 2: Zero-Trust Role Gateways
───────────────────────────────────────────────────────────
JWT decoding, token validation, and RBAC enforcement layer.

SECURITY CONTRACT
─────────────────
• Incoming chat tokens are handled out-of-band to enforce hard authentication boundaries.
• Role claims are extracted exclusively from cryptographically signed JWT strings.
• Fields are validated for expiration and type safety before being allowed to trigger tools.
• Both "role" (str) and "roles" (list) JWT formats are accepted for compatibility with
  the dev token endpoint, which may produce either.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()
_bearer = HTTPBearer()

# ── Role Constants (Synchronized with Database RoleEnum) ──────────────────────
ROLE_STUDENT = "student"
ROLE_LECTURER = "lecturer"
ROLE_ADMIN = "admin"
VALID_ROLES = {ROLE_STUDENT, ROLE_LECTURER, ROLE_ADMIN}


# ── Validated User Session Memory ─────────────────────────────────────────────
class UserSession(BaseModel):
    """
    Decoded and validated identity token mapped to every authenticated request.
    Feeds identity details directly into the LangGraph state engine.
    """

    user_id: str
    email: str
    role: str
    faculty_id: int | None = None

    @property
    def is_lecturer(self) -> bool:
        return self.role in [ROLE_LECTURER, ROLE_ADMIN]

    @property
    def is_student(self) -> bool:
        return self.role == ROLE_STUDENT

    @property
    def primary_role(self) -> str:
        """Returns the primary string role to govern supervisor node evaluations."""
        return self.role


# ── Cryptographic Token Management ────────────────────────────────────────────
def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    payload = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload["exp"] = expire
    payload["iat"] = datetime.now(timezone.utc)

    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def _extract_role(payload: dict[str, Any]) -> str | None:
    """
    Extracts the role from a JWT payload, handling both formats:
      - "role": "student"          (standard single-role string)
      - "roles": ["student", ...]  (legacy list format from dev token endpoint)

    Returns the resolved role string, or None if neither key is present.
    """
    # Prefer the canonical singular "role" key
    if "role" in payload and isinstance(payload["role"], str):
        return payload["role"]

    # Fall back to "roles" list — take the first non-empty entry
    if "roles" in payload and isinstance(payload["roles"], list) and payload["roles"]:
        return str(payload["roles"][0])

    return None


def _decode_token(token: str) -> dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate system access credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        print("🔍 STEP 1 PASSED: Token signature is cryptographically valid!")
        print("🚀 RAW FLASK PAYLOAD DATA RECEIVED:", payload)
    except ExpiredSignatureError:
        print("❌ CRASH: Token signature has expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session security token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as je:
        print(f"❌ TRIPWIRE A FAILED: Cryptographic decode failed. Reason: {je}")
        raise credentials_exception

    # Enforce token payload completeness checks
    if not {"sub"}.issubset(payload):
        print(f"❌ TRIPWIRE B FAILED: Payload keys are missing 'sub'. Found keys: {list(payload.keys())}")
        raise credentials_exception

    # Resolve role from either "role" or "roles" key
    resolved_role = _extract_role(payload)
    if not resolved_role:
        print("❌ TRIPWIRE C FAILED: Could not find 'role' or 'roles' keys inside the token dictionary.")
        raise credentials_exception

    print("✅ SUCCESS: Token passed all security checks!")
    payload["role"] = resolved_role
    return payload


# ── FastAPI Dependency Injections ─────────────────────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> UserSession:
    """
    FastAPI boundary dependency extracting identity states from the Authorization header.
    """
    payload = _decode_token(credentials.credentials)
    
    # 🚀 UPDATE THIS RETURN STATEMENT Safely:
    return UserSession(
        user_id=payload["sub"],                                # Extracts '56' perfectly
        email=payload.get("email", f"{payload['sub']}@student.edu.eg"), # Fallback string since Flask left it out
        role=payload["role"],                                  # Extracts 'student' perfectly
        faculty_id=payload.get("faculty_id"),
    )


async def require_lecturer(user: UserSession = Depends(get_current_user)) -> UserSession:
    """Raises a 403 Forbidden error if a student tries to access faculty endpoint boundaries."""
    if not user.is_lecturer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Instructor or Administrator privilege is required for this action.",
        )
    return user