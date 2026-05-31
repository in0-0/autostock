from __future__ import annotations

import re


def sanitize_error_message(exc: Exception | str) -> str:
    message = str(exc) or exc.__class__.__name__
    message = re.sub(r"https?://\S+", "[url]", message)
    message = re.sub(r"(/Users/\S+|/private/\S+|/var/\S+|[A-Za-z]:\\\S+)", "[path]", message)
    message = re.sub(
        r"(?i)(?:^|(?<=\s))((?:\.{1,2}/)?(?:[\w.-]+/)*[\w.-]*(?:credential|secret|token|service-account|account)[\w.-]*\.(?:json|ya?ml|toml|env|txt))",
        "[path]",
        message,
    )
    secret_key = (
        r"token|secret|credential|credentials_path|credential_path|password|api[_-]?key|"
        r"spreadsheet[_-]?id|sheet[_-]?id|account[_-]?id|chat[_-]?id|client[_-]?email"
    )
    quoted_secret_pattern = rf"(?i)['\"]?({secret_key})['\"]?\s*:\s*(['\"])[^'\"]*\2"
    message = re.sub(quoted_secret_pattern, lambda match: f"{match.group(1)}=[redacted]", message)
    secret_key_pattern = rf"(?i)\b({secret_key})\b\s*(?:=|:)?\s*[^\s,;}}]+"
    message = re.sub(secret_key_pattern, lambda match: f"{match.group(1)}=[redacted]", message)
    message = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[id]", message)
    return message
