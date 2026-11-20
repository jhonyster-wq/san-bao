import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña en texto plano coincide con el hash bcrypt."""
    try:
        plain_bytes = plain_password.encode("utf-8")
        # Truncar a 72 bytes para evitar límite de bcrypt si la contraseña fuera excesivamente larga
        plain_bytes = plain_bytes[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(plain_bytes, hash_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Genera un hash seguro con sal aleatoria utilizando Bcrypt."""
    plain_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_bytes, salt)
    return hashed.decode("utf-8")


def create_access_token(subject: str | Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Crea un JSON Web Token (JWT) de acceso firmado con expiración.
    Permite asociar el ID de usuario ('sub') y metadatos complementarios.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    if isinstance(subject, dict):
        to_encode.update(subject)
    else:
        to_encode["sub"] = str(subject)

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un refresh token con mayor periodo de expiración para renovar la sesión."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """Decodifica y valida la firma y expiración de un JWT."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError as e:
        raise ValueError(f"Token inválido o expirado: {str(e)}")


# =============================================================================
# FASE 8 (REQUERIMIENTO M): CIFRADO AES-256 CON GESTIÓN SEPARADA DE CLAVES Y PROTECCIÓN DE LOGS
# =============================================================================
class AES256FieldCipher:
    """
    Cifrador simétrico autenticado AES-256-GCM para campos clínicos y personales sensibles (Ley 20.584 / Ley 21.719).
    Utiliza una clave maestra estrictamente separada de la clave de firma JWT (FIELD_ENCRYPTION_KEY != SECRET_KEY).
    """

    PREFIX = "AES256GCM$"

    @classmethod
    def _derive_256bit_key(cls, raw_key: Optional[str] = None) -> bytes:
        import hashlib

        key_material = raw_key or settings.FIELD_ENCRYPTION_KEY
        if key_material == settings.SECRET_KEY:
            raise ValueError("Violación de Seguridad (Req. M): La clave de cifrado AES-256 debe estar separada de SECRET_KEY.")
        return hashlib.sha256(key_material.encode("utf-8")).digest()  # 32 bytes = 256 bits exactos

    @classmethod
    def encrypt(cls, plaintext: str, raw_key: Optional[str] = None) -> str:
        import os
        import base64
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if plaintext is None:
            return ""
        text_str = str(plaintext)
        if text_str.startswith(cls.PREFIX):
            return text_str
        key = cls._derive_256bit_key(raw_key)
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, text_str.encode("utf-8"), associated_data=b"SANBAO_AES256_V1")
        token_b64 = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return f"{cls.PREFIX}{token_b64}"

    @classmethod
    def decrypt(cls, encrypted_value: str, raw_key: Optional[str] = None) -> str:
        import base64
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if not encrypted_value:
            return ""
        text_str = str(encrypted_value)
        if not text_str.startswith(cls.PREFIX):
            return text_str
        raw_b64 = text_str[len(cls.PREFIX):]
        raw_bytes = base64.urlsafe_b64decode(raw_b64.encode("ascii"))
        nonce, ciphertext = raw_bytes[:12], raw_bytes[12:]
        key = cls._derive_256bit_key(raw_key)
        aesgcm = AESGCM(key)
        decrypted = aesgcm.decrypt(nonce, ciphertext, associated_data=b"SANBAO_AES256_V1")
        return decrypted.decode("utf-8")


def sanitize_sensitive_log_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Protección de Logs (Requerimiento M):
    Enmascara contraseñas, tokens, claves y campos clínicos de anamnesis antes de escribir en logs.
    """
    sensitive_keys = {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "traditional_anamnesis",
        "reason_for_consultation",
        "current_illness_history",
        "tongue_diagnosis",
        "pulse_diagnosis",
    }
    sanitized: Dict[str, Any] = {}
    for k, v in (payload or {}).items():
        if k.lower() in sensitive_keys:
            sanitized[k] = "***REDACTED_PROTECTED_LOG***"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_sensitive_log_payload(v)
        else:
            sanitized[k] = v
    return sanitized

