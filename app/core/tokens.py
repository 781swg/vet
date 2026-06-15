from app.core.config import get_settings

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover
    Fernet = None


def encrypt_token(token: str) -> str:
    key = get_settings().token_encryption_key
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is required to store encrypted tokens; use token_ref for external secret storage")
    if Fernet is None:
        raise RuntimeError("cryptography is required for token encryption")
    return Fernet(key.encode("utf-8")).encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(token_ref: str) -> str:
    key = get_settings().token_encryption_key
    if token_ref.startswith("ref:env:"):
        return token_ref.removeprefix("ref:env:")
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is required to decrypt token_ref")
    if Fernet is None:
        raise RuntimeError("cryptography is required for token encryption")
    return Fernet(key.encode("utf-8")).decrypt(token_ref.encode("utf-8")).decode("utf-8")
