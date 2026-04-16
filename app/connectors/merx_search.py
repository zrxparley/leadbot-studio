import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig
from app.connectors.merx_notice import MerxNoticeConnector


class MerxSearchConnector:
    base_url = "https://www.merx.com"
    search_url = "https://www.merx.com/public/solicitations/open"
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"

    def __init__(
        self,
        *,
        max_results: int = 4,
        search_timeout_seconds: int = 20,
        page_timeout_seconds: int = 20,
    ) -> None:
        self.max_results = max_results
        self.search_timeout_seconds = search_timeout_seconds
        self.notice_connector = MerxNoticeConnector(page_timeout_seconds=page_timeout_seconds)

    def fetch(self, config: LeadQueryConfig) -> list[RawLeadRecord]:
        leads: list[RawLeadRecord] = []
        seen_urls: set[str] = set()
        search_phrases = self._search_phrases(config.query)
        keywords = self._normalize_keywords(config.query)
        for phrase in search_phrases:
            try:
                response = requests.get(
                    self.search_url,
                    params={"keywords": phrase},
                    headers={"User-Agent": self.user_agent},
                    timeout=self.search_timeout_seconds,
                )
                response.raise_for_status()
            except requests.RequestException:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.select("a[href]"):
                href = anchor.get("href", "").strip()
                title = anchor.get_text(" ", strip=True)
                if not href or not title or "/solicitations/" not in href:
                    continue
                if "Published" not in title and "day(s) left" not in title:
                    continue
                if keywords and not self._matches_keywords(title, keywords):
                    continue
                detail_url = urljoin(self.base_url, href)
                normalized_url = self._normalize_result_url(detail_url)
                if not normalized_url or normalized_url in seen_urls:
                    continue
                notice = self.notice_connector.fetch_url(
                    normalized_url,
                    product_hint=config.product_interest,
                )
                if not notice:
                    continue
                seen_urls.add(normalized_url)
                leads.append(notice)
                if len(leads) >= self.max_results:
                    return leads
        return leads

    @staticmethod
    def _matches_keywords(title: str, keywords: list[str]) -> bool:
        lowered = title.lower()
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _normalize_keywords(query: str) -> list[str]:
        tokens = re.split(r"[,\s]+", query.lower())
        return [token for token in tokens if len(token) >= 4]

    @staticmethod
    def _search_phrases(query: str) -> list[str]:
        phrases = [part.strip() for part in query.split(",") if part.strip()]
        return phrases or [query.strip()]

    @staticmethod
    def _normalize_result_url(url: str) -> str | None:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return normalized
