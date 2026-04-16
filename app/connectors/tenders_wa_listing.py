import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig


class TendersWAListingConnector:
    base_url = "https://www.tenders.wa.gov.au"
    listing_url = (
        "https://www.tenders.wa.gov.au/watenders/tender/search/"
        "tender-search.action?action=advanced-tender-search-open-tender"
    )
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"

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
        leads: list[RawLeadRecord] = []
        seen_urls: set[str] = set()
        for anchor in soup.select("a[href*='/watenders/tender/display/tender-details.action?id=']"):
            href = anchor.get("href", "").strip()
            title = anchor.get_text(" ", strip=True)
            if not href or not title:
                continue
            normalized_title = title.lower()
            if keywords and not any(keyword in normalized_title for keyword in keywords):
                continue
            detail_url = urljoin(self.base_url, href)
            if detail_url in seen_urls:
                continue
            record = self._fetch_detail(detail_url, product_hint=config.product_interest)
            if not record:
                continue
            seen_urls.add(detail_url)
            leads.append(record)
            if len(leads) >= self.max_results:
                break
        return leads

    def _fetch_detail(self, url: str, *, product_hint: str | None) -> RawLeadRecord | None:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=self.page_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text("\n", strip=True)
        company_name = self._extract_value_after_label(text, "Issued by") or "Western Australia Public Buyer"
        title = self._extract_page_title(soup)
        request_number = self._extract_value_after_label(text, "Number:")
        buyer_contact_name = self._extract_value_after_label(text, "Person")
        contact_phone = self._extract_value_after_label(text, "Phone") or self._extract_value_after_label(text, "Mobile")
        contact_email = self._extract_value_after_label(text, "Email")
        demand_summary = self._extract_description(text) or title
        demand_posted_at = self._extract_closing_date(text)

        if not demand_posted_at or not (contact_email or contact_phone):
            return None

        return RawLeadRecord(
            source_name="tenders-wa-listing",
            company_name=company_name,
            website=self._website_from_url(str(response.url)),
            country="Australia",
            description=demand_summary,
            source_url=str(response.url),
            contact_hint=str(response.url),
            product_hint=product_hint,
            search_query=request_number or title,
            demand_summary=title,
            demand_posted_at=demand_posted_at,
            buyer_contact_name=buyer_contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            demand_type="public_procurement_notice",
        )

    @staticmethod
    def _extract_value_after_label(text: str, label: str) -> str | None:
        lines = [line.strip() for line in text.splitlines()]
        for index, line in enumerate(lines):
            if line != label and line != f"{label}:":
                continue
            for next_line in lines[index + 1 :]:
                if not next_line:
                    continue
                if next_line.endswith(":"):
                    break
                return re.sub(r"\s+", " ", next_line).strip()
        return None

    @staticmethod
    def _extract_page_title(soup: BeautifulSoup) -> str:
        text = soup.get_text("\n", strip=True)
        match = re.search(r"Comments\s+(.*?)\s+Issued by", text, flags=re.DOTALL)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        return title.replace("Tenders WA | ", "").strip()

    @staticmethod
    def _extract_description(text: str) -> str:
        match = re.search(
            r"Description\s+(.*?)\s+Responses\s+Closes",
            text,
            flags=re.DOTALL,
        )
        if not match:
            return ""
        return re.sub(r"\s+", " ", match.group(1)).strip()[:1200]

    @staticmethod
    def _extract_closing_date(text: str) -> datetime | None:
        match = re.search(r"Closes\s+[A-Za-z]{3},\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", text)
        if not match:
            return None
        try:
            return datetime.strptime(match.group(1), "%d %b %Y")
        except ValueError:
            return None

    @staticmethod
    def _normalize_keywords(query: str) -> list[str]:
        tokens = re.split(r"[,\s]+", query.lower())
        return [token for token in tokens if len(token) >= 4]

    @staticmethod
    def _website_from_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
