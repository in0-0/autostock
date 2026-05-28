from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=target.parent,
            delete=False,
            suffix=f".{target.name}.tmp",
            encoding="utf-8",
        ) as tf:
            temp_name = tf.name
            json.dump(data, tf, ensure_ascii=False, indent=2, default=str)
            tf.write("\n")
            tf.flush()
            os.fsync(tf.fileno())

        os.replace(temp_name, target)
        dir_fd = os.open(target.parent, os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        if temp_name and os.path.exists(temp_name):
            os.remove(temp_name)
        raise
