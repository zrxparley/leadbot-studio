import re
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig


class CanadaBuysNoticeConnector:
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"

    def __init__(self, *, page_timeout_seconds: int = 18) -> None:
        self.page_timeout_seconds = page_timeout_seconds

    def fetch(self, config: LeadQueryConfig) -> list[RawLeadRecord]:
        if not config.url:
            return []
        notice = self._fetch_notice(config.url, product_hint=config.product_interest)
        return [notice] if notice else []

    def _fetch_notice(self, url: str, *, product_hint: str | None) -> RawLeadRecord | None:
        try:
            response = requests.get(
                url,
                timeout=self.page_timeout_seconds,
                headers={"User-Agent": self.user_agent},
                allow_redirects=True,
            )
            response.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text("\n", strip=True)

        solicitation_number = self._extract_value_after_label(text, "Solicitation number")
        published_at = self._extract_date_after_label(text, "Publication date")
        organization = self._extract_value_after_label(text, "Organization")
        contact_name = self._extract_value_after_label(text, "Contracting authority")
        contact_phone = self._extract_value_after_label(text, "Phone")
        contact_email = self._extract_value_after_label(text, "Email")
        description = self._extract_description(text)
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        demand_summary = self._clean_title(title)

        if not published_at or not organization or not (contact_email or contact_phone):
            return None

        if contact_phone and len(re.sub(r"\D", "", contact_phone)) < 7:
            contact_phone = None
        if not contact_email and not contact_phone:
            return None

        return RawLeadRecord(
            source_name="canadabuys-notice",
            company_name=organization,
            website=self._website_from_url(str(response.url)),
            country="Canada",
            description=description or demand_summary,
            source_url=str(response.url),
            contact_hint=str(response.url),
            product_hint=product_hint,
            search_query=solicitation_number or demand_summary,
            demand_summary=demand_summary,
            demand_posted_at=published_at,
            buyer_contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            demand_type="public_procurement_notice",
        )

    @staticmethod
    def _extract_value_after_label(text: str, label: str) -> str | None:
        lines = [line.strip() for line in text.splitlines()]
        for index, line in enumerate(lines):
            if line != label:
                continue
            for next_line in lines[index + 1 :]:
                if not next_line:
                    continue
                if next_line.endswith(":"):
                    break
                return re.sub(r"\s+", " ", next_line).strip()
        return None

    @staticmethod
    def _extract_date_after_label(text: str, label: str) -> datetime | None:
        value = CanadaBuysNoticeConnector._extract_value_after_label(text, label)
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y/%m/%d")
        except ValueError:
            return None

    @staticmethod
    def _extract_description(text: str) -> str:
        match = re.search(
            r"Description\s+(.*?)\s+(?:Show more description|Contract duration|Trade agreements|Contact information)",
            text,
            flags=re.DOTALL,
        )
        if not match:
            return ""
        return re.sub(r"\s+", " ", match.group(1)).strip()[:1200]

    @staticmethod
    def _clean_title(title: str) -> str:
        cleaned = title.replace(" - Tender Notice | CanadaBuys", "").strip()
        return re.sub(r"\s+", " ", cleaned)

    @staticmethod
    def _website_from_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
