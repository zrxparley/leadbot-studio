from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from app.connectors.base import RawNewsRecord
from app.connectors.source_registry import NewsSourceConfig


class RSSNewsConnector:
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"

    def fetch(self, source: NewsSourceConfig) -> list[RawNewsRecord]:
        response = requests.get(
            source.url,
            timeout=15,
            headers={"User-Agent": self.user_agent},
        )
        response.raise_for_status()

        root = ElementTree.fromstring(response.content)
        records: list[RawNewsRecord] = []

        for item in root.findall(".//item"):
            title = self._text(item.findtext("title"))
            link = self._text(item.findtext("link"))
            body = self._strip_html(item.findtext("description"))
            published_at = self._parse_published_at(item.findtext("pubDate"))

            if not title or not link:
                continue

            records.append(
                RawNewsRecord(
                    source_name=source.name,
                    title=title,
                    url=link,
                    body=body or title,
                    published_at=published_at,
                    country=source.country,
                    language=source.language,
                )
            )

        return records

    @staticmethod
    def _parse_published_at(value: str | None) -> datetime:
        if not value:
            return datetime.now(UTC).replace(tzinfo=None)
        try:
            return parsedate_to_datetime(value).replace(tzinfo=None)
        except (TypeError, ValueError, IndexError):
            return datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def _strip_html(value: str | None) -> str:
        if not value:
            return ""
        html = unescape(value)
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    @staticmethod
    def _text(value: str | None) -> str:
        return (value or "").strip()
