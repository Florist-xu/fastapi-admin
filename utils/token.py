import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


JWT_SECRET = "change-this-to-a-strong-secret"
JWT_ALG = "HS256"
ACCESS_EXPIRE_MINUTES = 60
REFRESH_EXPIRE_DAYS = 7


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("utf-8"))


def _sign(message: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(signature)


def create_jwt(payload: Dict[str, Any], expire_delta: timedelta) -> str:
    header = {"alg": JWT_ALG, "typ": "JWT"}
    now = datetime.now(timezone.utc)
    body = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + expire_delta).timestamp()),
    }
    header_part = _b64url_encode(
        json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    payload_part = _b64url_encode(
        json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    sign_part = _sign(signing_input, JWT_SECRET)
    return f"{header_part}.{payload_part}.{sign_part}"


def create_token_pair(user_id: str, username: str) -> Dict[str, str]:
    access_token = create_jwt(
        {"sub": user_id, "username": username, "type": "access"},
        timedelta(minutes=ACCESS_EXPIRE_MINUTES),
    )
    refresh_token = create_jwt(
        {"sub": user_id, "username": username, "type": "refresh"},
        timedelta(days=REFRESH_EXPIRE_DAYS),
    )
    return {"token": access_token, "refreshToken": refresh_token}


def verify_jwt(token: str, token_type: Optional[str] = "access") -> Optional[Dict[str, Any]]:
    try:
        header_part, payload_part, sign_part = token.split(".", 2)
        signing_input = f"{header_part}.{payload_part}".encode("utf-8")
        expected_sign = _sign(signing_input, JWT_SECRET)
        if not hmac.compare_digest(sign_part, expected_sign):
            return None

        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
        exp = int(payload.get("exp", 0))
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if exp <= now_ts:
            return None
        if token_type and payload.get("type") != token_type:
            return None
        return payload
    except Exception:
        return None
