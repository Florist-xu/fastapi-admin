import base64
import hashlib
import hmac
import os


PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 260000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("utf-8")
    digest_b64 = base64.b64encode(digest).decode("utf-8")
    return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt_b64}${digest_b64}"


def verify_password(password: str, stored_password: str) -> bool:
    if not isinstance(password, str) or not isinstance(stored_password, str):
        return False

    pwd = password
    stored = stored_password
    try:
        algorithm, iter_str, salt_b64, digest_b64 = stored.split("$", 3)
        if algorithm != PBKDF2_ALGORITHM:
            return False
        iterations = int(iter_str)
        salt = base64.b64decode(salt_b64)
        expected_digest = base64.b64decode(digest_b64)
    except Exception:
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        pwd.encode("utf-8"),
        salt,
        iterations,
    )
    if hmac.compare_digest(actual_digest, expected_digest):
        return True

    # Compatibility: tolerate accidental surrounding spaces in historical data/input.
    if pwd != pwd.strip():
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            pwd.strip().encode("utf-8"),
            salt,
            iterations,
        )
        if hmac.compare_digest(actual_digest, expected_digest):
            return True

    return False
