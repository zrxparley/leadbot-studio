import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig


class TasmaniaTendersListingConnector:
    base_url = "https://www.tenders.tas.gov.au"
    listing_url = "https://www.tenders.tas.gov.au/OpenForBids/List/Public/ClosingDate"
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"
    email_pattern = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
    phone_pattern = re.compile(r"(?:\+\d{1,3}\s*)?(?:\(?\d{2,4}\)?[\s.-]*){2,}\d{2,4}")

    def __init__(
        self,
        *,
        max_results: int = 4,
        listing_timeout_seconds: int = 20,
        page_timeout_seconds: int = 20,
    ) -> None:
        self.max_results = max_results
        self.listing_timeout_seconds = listing_timeout_seconds
        self.page_timeout_seconds = page_timeout_seconds

    def fetch(self, config: LeadQueryConfig) -> list[RawLeadRecord]:
        try:
            response = requests.get(
                self.listing_url,
                headers={"User-Agent": self.user_agent},
                timeout=self.listing_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        keywords = self._normalize_keywords(config.query)
        records: list[RawLeadRecord] = []
        seen_urls: set[str] = set()
        for anchor in soup.select('a[href*="/OpenForBids/Details/"]'):
            href = anchor.get("href", "").strip()
            title = anchor.get_text(" ", strip=True)
            if not href or not title:
                continue
            if keywords and not self._matches_keywords(title=title, keywords=keywords):
                continue
            detail_url = urljoin(self.base_url, href)
            if detail_url in seen_urls:
                continue
            record = self._fetch_detail(detail_url, fallback_title=title, product_hint=config.product_interest)
            if not record:
                continue
            seen_urls.add(detail_url)
            records.append(record)
            if len(records) >= self.max_results:
                break
        return records

    def _fetch_detail(
        self,
        url: str,
        *,
        fallback_title: str,
        product_hint: str | None,
    ) -> RawLeadRecord | None:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.user_agent, "Referer": self.listing_url},
                timeout=self.page_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        title = self._extract_field_value(soup, "Procurement Title") or fallback_title
        agency_block = self._extract_field_value(soup, "Agency", separator="\n")
        company_name = self._first_line(agency_block) or "Tasmania Public Buyer"
        description = self._extract_field_value(soup, "Description")
        enquiries = self._extract_field_value(soup, "Enquiries")
        applications = self._extract_field_value(soup, "Applications must be lodged at")
        contact_name = self._extract_contact_name(enquiries)
        contact_email = self._extract_email(enquiries) or self._extract_email(applications)
        contact_phone = self._extract_phone(enquiries)
        demand_posted_at = self._extract_closing_date(
            self._extract_field_value(soup, "Closing Date and Time")
        )
        notice_number = self._extract_field_value(soup, "Unique Tender ID")

        if not demand_posted_at or not (contact_email or contact_phone):
            return None

        return RawLeadRecord(
            source_name="tasmania-tenders-listing",
            company_name=company_name,
            website=self._website_from_url(str(response.url)),
            country="Australia",
            description=description or title,
            source_url=str(response.url),
            contact_hint=str(response.url),
            product_hint=product_hint,
            search_query=notice_number or title,
            demand_summary=title,
            demand_posted_at=demand_posted_at,
            buyer_contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            demand_type="public_procurement_notice",
        )

    @staticmethod
    def _matches_keywords(*, title: str, keywords: list[str]) -> bool:
        lowered = title.lower()
        return any(keyword in lowered for keyword in keywords)

    @staticmethod
    def _normalize_keywords(query: str) -> list[str]:
        tokens = re.split(r"[,\s]+", query.lower())
        return [token for token in tokens if len(token) >= 4]

    @staticmethod
    def _extract_field_value(soup: BeautifulSoup, label_text: str, *, separator: str = " ") -> str | None:
        label = soup.find("label", string=lambda value: value and label_text in value)
        if not label or not label.parent:
            return None
        value_node = label.parent.find_next_sibling("div")
        if not value_node:
            return None
        raw_value = value_node.get_text(separator, strip=True)
        value = re.sub(r"\s+", " ", raw_value).strip(" .") if separator == " " else raw_value.strip()
        return value[:300] if value else None

    def _extract_email(self, text: str | None) -> str | None:
        if not text:
            return None
        matches = self.email_pattern.findall(text)
        if not matches:
            return None
        for email in matches:
            lowered = email.lower()
            if "tenders@" in lowered and len(matches) > 1:
                continue
            return email
        return matches[0]

    def _extract_phone(self, text: str | None) -> str | None:
        if not text:
            return None
        mobile_match = re.search(r"Mobile:\s*([^\n]+)", text)
        if mobile_match:
            phone = mobile_match.group(1).split("Email:")[0]
            phone = re.sub(r"\s+", " ", phone).strip()
            if len(re.sub(r"\D", "", phone)) >= 7:
                return phone
        phone_match = re.search(r"Phone:\s*([^\n]+)", text)
        if phone_match:
            phone = phone_match.group(1).split("Email:")[0]
            phone = re.sub(r"\s+", " ", phone).strip()
            if len(re.sub(r"\D", "", phone)) >= 7:
                return phone
        generic_match = self.phone_pattern.search(text)
        if not generic_match:
            return None
        phone = re.sub(r"\s+", " ", generic_match.group(0)).strip()
        return phone if len(re.sub(r"\D", "", phone)) >= 7 else None

    @staticmethod
    def _extract_contact_name(text: str | None) -> str | None:
        if not text:
            return None
        match = re.search(r"^([A-Z][A-Za-z .'-]+)\s+(?:Mobile:|Phone:|Email:)", text)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" .")
        return None

    @staticmethod
    def _extract_closing_date(text: str | None) -> datetime | None:
        if not text:
            return None
        match = re.search(r"(\d{2}/\d{2}/\d{4})", text)
        if not match:
            return None
        try:
            return datetime.strptime(match.group(1), "%d/%m/%Y")
        except ValueError:
            return None

    @staticmethod
    def _first_line(text: str | None) -> str | None:
        if not text:
            return None
        for line in text.splitlines():
            cleaned = line.strip()
            if cleaned:
                return cleaned
        return None

    @staticmethod
    def _website_from_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
