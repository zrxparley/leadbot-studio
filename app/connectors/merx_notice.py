import re
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig
from app.services.public_contact_enricher import PublicContactEnricher


class MerxNoticeConnector:
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"
    email_pattern = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
    phone_pattern = re.compile(r"(?:\+\d{1,3}\s*)?(?:\(?\d{2,4}\)?[\s.-]*){2,}\d{2,4}")

    def __init__(self, *, page_timeout_seconds: int = 20) -> None:
        self.page_timeout_seconds = page_timeout_seconds
        self.contact_enricher = PublicContactEnricher(timeout_seconds=10)

    def fetch(self, config: LeadQueryConfig) -> list[RawLeadRecord]:
        if not config.url:
            return []
        notice = self.fetch_url(config.url, product_hint=config.product_interest)
        return [notice] if notice else []

    def fetch_url(self, url: str, *, product_hint: str | None) -> RawLeadRecord | None:
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
        company_name = self._extract_value_after_label(text, "Issuing Organization")
        published_at = self._extract_merx_datetime(text, "Publication")
        title = self._extract_value_after_label(text, "Title") or self._clean_title(
            soup.title.get_text(" ", strip=True) if soup.title else ""
        )
        description = self._extract_description(text)
        contact_name, contact_email, contact_phone = self._extract_contact_information(text)

        if company_name and contact_email and not contact_phone:
            enriched = self.contact_enricher.enrich(company_name=company_name, country="Canada")
            if enriched and enriched.phone:
                contact_phone = enriched.phone

        if not company_name or not published_at or not (contact_email or contact_phone):
            return None

        return RawLeadRecord(
            source_name="merx-notice",
            company_name=company_name,
            website=self._website_from_url(str(response.url)),
            country="Canada",
            description=description or title,
            source_url=str(response.url),
            contact_hint=str(response.url),
            product_hint=product_hint,
            search_query=(
                self._extract_value_after_label(text, "Solicitation Number")
                or self._extract_value_after_label(text, "Project Number")
                or title
            ),
            demand_summary=title,
            demand_posted_at=published_at,
            buyer_contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            demand_type="public_procurement_notice",
        )

    @staticmethod
    def _extract_value_after_label(text: str, label: str) -> str | None:
        pattern = re.compile(
            rf"{re.escape(label)}\s+(.+?)(?:\n(?:[A-Z][A-Za-z/& ,.-]+|##|###)|$)",
            flags=re.DOTALL,
        )
        match = pattern.search(text)
        if not match:
            return None
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .")
        return value[:300] if value else None

    @staticmethod
    def _extract_merx_datetime(text: str, label: str) -> datetime | None:
        value = MerxNoticeConnector._extract_value_after_label(text, label)
        if not value:
            return None
        value = value.replace("A - Previous Amendment", "").strip()
        value = re.sub(r"\b(?:EST|EDT|CST|CDT|MST|MDT|PST|PDT|AST|ADT)\b", "", value).strip()
        value = re.sub(r"\s+", " ", value)
        for fmt in ("%Y/%m/%d %I:%M:%S %p", "%Y/%m/%d %I:%M %p", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _extract_description(text: str) -> str:
        match = re.search(r"Description\s+(.+?)\s+Dates\s+Publication", text, flags=re.DOTALL)
        if not match:
            return ""
        return re.sub(r"\s+", " ", match.group(1)).strip(" .")[:1200]

    def _extract_contact_information(self, text: str) -> tuple[str | None, str | None, str | None]:
        match = re.search(
            r"Contact Information\s+([A-Z][A-Za-z .'-]+)\s+(.*?)(?:Buyer Preferences|Bid Submission Process|Documents|Print Options)",
            text,
            flags=re.DOTALL | re.I,
        )
        if not match:
            return None, None, None
        contact_name = re.sub(r"\s+", " ", match.group(1)).strip(" .")
        trailing = match.group(2)
        email_match = self.email_pattern.search(trailing)
        contact_email = email_match.group(0).strip() if email_match else None
        phone_match = self.phone_pattern.search(trailing)
        contact_phone = None
        if phone_match:
            candidate = re.sub(r"\s+", " ", phone_match.group(0)).strip()
            if len(re.sub(r"\D", "", candidate)) >= 7:
                contact_phone = candidate
        return contact_name, contact_email, contact_phone

    @staticmethod
    def _clean_title(title: str) -> str:
        cleaned = title.replace("| MERX", "").strip()
        return re.sub(r"\s+", " ", cleaned).strip(" -")

    @staticmethod
    def _website_from_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
