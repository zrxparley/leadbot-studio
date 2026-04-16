import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig


class EasyTendersNoticeConnector:
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"
    phone_pattern = re.compile(r"\+?\d[\d\s()./-]{7,}\d")

    def __init__(self, *, page_timeout_seconds: int = 12) -> None:
        self.page_timeout_seconds = page_timeout_seconds

    def fetch(self, config: LeadQueryConfig) -> list[RawLeadRecord]:
        if not config.url:
            return []
        notice = self._fetch_notice(
            config.url,
            country=config.country,
            product_hint=config.product_interest,
        )
        return [notice] if notice else []

    def _fetch_notice(
        self,
        url: str,
        *,
        country: str,
        product_hint: str | None,
    ) -> RawLeadRecord | None:
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

        company_name = self._extract_value_after_label(text, "Department:") or "EasyTenders Buyer"
        demand_summary = self._extract_value_after_label(text, "Bid Description:") or ""
        buyer_contact_name = (
            self._extract_value_after_label(text, "Enquiries/Contact Person:")
            or self._extract_value_after_label(text, "Contact Person:")
        )
        contact_email = self._extract_cf_email(soup)
        contact_phone = self._extract_value_after_label(text, "Tel :")
        if not contact_phone:
            contact_phone = self._extract_best_phone(text)
        if not contact_email and not contact_phone:
            return None

        demand_posted_at = (
            self._extract_datetime_after_label(text, "Imported on:")
            or self._extract_datetime_after_label(text, "Modified Date:")
            or self._extract_date_after_label(text, "Opening Date:")
        )
        if not demand_posted_at:
            return None

        original_source_url = self._extract_original_source_url(soup, base_url=str(response.url))

        return RawLeadRecord(
            source_name="easytenders-notice",
            company_name=company_name,
            website=self._website_from_url(original_source_url or str(response.url)),
            country=country,
            description=demand_summary or company_name,
            source_url=str(response.url),
            contact_hint=original_source_url or str(response.url),
            product_hint=product_hint,
            search_query=soup.title.get_text(" ", strip=True) if soup.title else company_name,
            demand_summary=demand_summary or company_name,
            demand_posted_at=demand_posted_at,
            buyer_contact_name=buyer_contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            demand_type="public_procurement_notice",
        )

    @staticmethod
    def _extract_value_after_label(text: str, label: str) -> str | None:
        match = re.search(re.escape(label) + r"\s*(.+)", text)
        if not match:
            return None
        value = match.group(1).splitlines()[0].strip()
        return re.sub(r"\s+", " ", value)

    @staticmethod
    def _extract_date_after_label(text: str, label: str) -> datetime | None:
        value = EasyTendersNoticeConnector._extract_value_after_label(text, label)
        if not value:
            return None
        for fmt in ("%A, %d %b %Y", "%d %b %Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _extract_datetime_after_label(text: str, label: str) -> datetime | None:
        value = EasyTendersNoticeConnector._extract_value_after_label(text, label)
        if not value:
            return None
        for fmt in ("%A, %d %b %Y %I:%M%p", "%d %b %Y %I:%M%p"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _extract_cf_email(soup: BeautifulSoup) -> str | None:
        encoded = soup.select_one("span.__cf_email__")
        if not encoded:
            return None
        cfemail = encoded.get("data-cfemail", "").strip()
        if not cfemail or len(cfemail) < 4 or len(cfemail) % 2 != 0:
            return None
        key = int(cfemail[:2], 16)
        decoded_chars = []
        for index in range(2, len(cfemail), 2):
            decoded_chars.append(chr(int(cfemail[index:index + 2], 16) ^ key))
        return "".join(decoded_chars)

    def _extract_best_phone(self, text: str) -> str | None:
        for phone in sorted(set(self.phone_pattern.findall(text))):
            digits = re.sub(r"\D", "", phone)
            if len(digits) < 8:
                continue
            return re.sub(r"\s+", " ", phone).strip()
        return None

    @staticmethod
    def _extract_original_source_url(soup: BeautifulSoup, *, base_url: str) -> str | None:
        for anchor in soup.select("a[href]"):
            text = anchor.get_text(" ", strip=True).lower()
            href = anchor.get("href", "").strip()
            if not href:
                continue
            if "view original" in text:
                return urljoin(base_url, href)
        return None

    @staticmethod
    def _website_from_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
