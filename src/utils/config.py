from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised on bare macOS Python installs.
    yaml = None


def load_settings(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        if yaml is not None:
            settings = yaml.safe_load(f) or {}
        else:
            settings = _load_simple_yaml(f.read())
    return settings


def get_nested(settings: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = settings
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _load_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any] | list[Any]]] = [(-1, root)]
    last_key_by_indent: dict[int, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if stripped.startswith("- "):
            value = _parse_scalar(stripped[2:].strip())
            if not isinstance(parent, list):
                grand_parent = stack[-2][1]
                list_key = last_key_by_indent[stack[-1][0]]
                new_list: list[Any] = []
                grand_parent[list_key] = new_list  # type: ignore[index]
                stack[-1] = (stack[-1][0], new_list)
                parent = new_list
            parent.append(value)  # type: ignore[union-attr]
            continue

        key, _, raw_value = stripped.partition(":")
        if raw_value.strip():
            parent[key] = _parse_scalar(raw_value.strip())  # type: ignore[index]
        else:
            child: dict[str, Any] = {}
            parent[key] = child  # type: ignore[index]
            last_key_by_indent[indent] = key
            stack.append((indent, child))

    return root


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {'""', "''"}:
        return ""
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip("\"'")
