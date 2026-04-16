import json
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass(slots=True)
class NotificationMessage:
    title: str
    markdown: str


class BaseNotifier:
    def send(self, title: str, markdown: str) -> None:
        raise NotImplementedError


class ConsoleNotifier(BaseNotifier):
    def send(self, title: str, markdown: str) -> None:
        print(f"[Notifier] {title}\n{markdown}")


class DingTalkNotifier(BaseNotifier):
    def __init__(self, webhook: str) -> None:
        self.webhook = webhook

    def send(self, title: str, markdown: str) -> None:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": markdown,
            },
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(self.webhook, content=json.dumps(payload))
            response.raise_for_status()


class NotifierFactory:
    def __init__(self) -> None:
        self.settings = get_settings()

    def create(self) -> BaseNotifier:
        if self.settings.dingtalk_webhook:
            return DingTalkNotifier(self.settings.dingtalk_webhook)
        return ConsoleNotifier()

