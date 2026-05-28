from __future__ import annotations

from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover - bare runtime can still render local reports.
    requests = None


MARKDOWN_V2_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"


def escape_markdown(text: str) -> str:
    return "".join(f"\\{char}" if char in MARKDOWN_V2_ESCAPE_CHARS else char for char in text)


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str, parse_mode: str = "MarkdownV2") -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str) -> None:
        if not self.enabled:
            return
        if requests is None:
            raise RuntimeError("requests package is required to send Telegram messages")
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        response = requests.post(
            url,
            json={"chat_id": self.chat_id, "text": text, "parse_mode": self.parse_mode},
            timeout=15,
        )
        response.raise_for_status()

    def send_document(self, path: str | Path, caption: str = "") -> None:
        if not self.enabled:
            return
        if requests is None:
            raise RuntimeError("requests package is required to send Telegram documents")
        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        with Path(path).open("rb") as f:
            response = requests.post(
                url,
                data={"chat_id": self.chat_id, "caption": caption},
                files={"document": f},
                timeout=30,
            )
        response.raise_for_status()
