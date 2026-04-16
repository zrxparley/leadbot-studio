from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from app.connectors.base import RawLeadRecord
from app.connectors.easytenders_notice import EasyTendersNoticeConnector
from app.connectors.lead_registry import LeadQueryConfig


@dataclass(slots=True)
class EasyTendersSearchResult:
    title: str
    url: str


class EasyTendersSearchConnector:
    search_endpoint = "https://html.duckduckgo.com/html/"
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"

    def __init__(
        self,
        *,
        max_results: int = 5,
        search_timeout_seconds: int = 15,
        page_timeout_seconds: int = 12,
    ) -> None:
        self.max_results = max_results
        self.search_timeout_seconds = search_timeout_seconds
        self.notice_connector = EasyTendersNoticeConnector(page_timeout_seconds=page_timeout_seconds)

    def fetch(self, config: LeadQueryConfig) -> list[RawLeadRecord]:
        response = requests.get(
            self.search_endpoint,
            params={"q": config.query},
            timeout=self.search_timeout_seconds,
            headers={"User-Agent": self.user_agent},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        records: list[RawLeadRecord] = []
        seen_urls: set[str] = set()
        for result in self._parse_results(soup):
            if len(records) >= self.max_results:
                break
            normalized_url = self._normalize_result_url(result.url)
            if not normalized_url or normalized_url in seen_urls:
                continue
            if "easytenders.co.za/tenders/" not in normalized_url:
                continue
            notice = self.notice_connector._fetch_notice(
                normalized_url,
                country=config.country,
                product_hint=config.product_interest,
            )
            if not notice:
                continue
            seen_urls.add(normalized_url)
            records.append(notice)
        return records

    @staticmethod
    def _parse_results(soup: BeautifulSoup) -> list[EasyTendersSearchResult]:
        results: list[EasyTendersSearchResult] = []
        for result in soup.select(".result"):
            title_link = result.select_one(".result__title a.result__a") or result.select_one("a.result__a")
            if not title_link:
                continue
            results.append(
                EasyTendersSearchResult(
                    title=title_link.get_text(" ", strip=True),
                    url=title_link.get("href", "").strip(),
                )
            )
        return results

    @staticmethod
    def _normalize_result_url(url: str) -> str | None:
        if not url:
            return None
        if url.startswith("//"):
            return f"https:{url}"
        if "duckduckgo.com/l/" not in url:
            return url
        parsed = urlparse(url)
        uddg = parse_qs(parsed.query).get("uddg")
        if not uddg:
            return None
        return unquote(uddg[0])
