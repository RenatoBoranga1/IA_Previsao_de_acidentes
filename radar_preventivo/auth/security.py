from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

DEFAULT_ITERATIONS = 390000
PASSWORD_SCHEME = "pbkdf2_sha256"


def hash_password(password: str, *, salt: str | None = None, iterations: int = DEFAULT_ITERATIONS) -> str:
    normalized_password = password.encode("utf-8")
    normalized_salt = (salt or secrets.token_hex(16)).encode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", normalized_password, normalized_salt, iterations)
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{PASSWORD_SCHEME}${iterations}${normalized_salt.decode('utf-8')}${encoded_digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, raw_iterations, salt, _expected_digest = password_hash.split("$", 3)
    except ValueError:
        return False

    if scheme != PASSWORD_SCHEME:
        return False

    candidate_hash = hash_password(
        password=password,
        salt=salt,
        iterations=int(raw_iterations),
    )
    return hmac.compare_digest(candidate_hash, password_hash)
