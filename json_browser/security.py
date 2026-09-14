from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_KEYWORDS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credential",
    "authorization",
    "auth",
    "bearer",
    "session",
    "cookie",
}


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)


def mask_value(value: Any) -> str:
    text = str(value)
    if not text:
        return "***"
    if len(text) <= 4:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def sanitize_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except Exception:
        return url
    netloc = parts.netloc
    if "@" in netloc:
        _, host = netloc.rsplit("@", 1)
        netloc = f"***@{host}"
    if parts.query:
        query_pairs = parse_qsl(parts.query, keep_blank_values=True)
        sanitized_pairs = []
        for key, value in query_pairs:
            sanitized_pairs.append((key, "***" if is_sensitive_key(key) else value))
        query = urlencode(sanitized_pairs, doseq=True)
    else:
        query = parts.query
    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


def sanitize_data(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized = {}
        for key, value in payload.items():
            if is_sensitive_key(key):
                sanitized[key] = "***"
                continue
            if key.lower() == "url" and isinstance(value, str):
                sanitized[key] = sanitize_url(value)
                continue
            sanitized[key] = sanitize_data(value)
        return sanitized
    if isinstance(payload, list):
        return [sanitize_data(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(sanitize_data(item) for item in payload)
    return payload
