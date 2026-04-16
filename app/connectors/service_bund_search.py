import re
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig
from app.services.public_contact_enricher import PublicContactEnricher


class ServiceBundNoticeConnector:
    base_url = "https://www.service.bund.de/"
    search_url = "https://www.service.bund.de/Content/DE/Ausschreibungen/Suche/Formular.html"
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"
    search_chunk_size = 32768

    def __init__(
        self,
        *,
        max_results: int = 4,
        search_timeout_seconds: int = 18,
        page_timeout_seconds: int = 18,
    ) -> None:
        self.max_results = max_results
        self.search_timeout_seconds = search_timeout_seconds
        self.page_timeout_seconds = page_timeout_seconds
        self.contact_enricher = PublicContactEnricher(timeout_seconds=page_timeout_seconds)

    def fetch(self, config: LeadQueryConfig) -> list[RawLeadRecord]:
        try:
            response = requests.get(
                self.search_url,
                params={
                    "nn": "4641482",
                    "type": "0",
                    "resultsPerPage": str(max(self.max_results * 5, 20)),
                    "templateQueryString": config.query,
                },
                headers={"User-Agent": self.user_agent},
                timeout=self.search_timeout_seconds,
                stream=True,
            )
            response.raise_for_status()
        except requests.RequestException:
            return []

        markup = self._read_search_markup(response)
        soup = BeautifulSoup(markup, "html.parser")
        leads: list[RawLeadRecord] = []
        seen_urls: set[str] = set()
        for anchor in soup.select("a[href*='IMPORTE/Ausschreibungen/']"):
            detail_url = self._normalize_url(urljoin(self.base_url, anchor.get("href", "").strip()))
            if not detail_url or detail_url in seen_urls:
                continue
            title = anchor.select_one("h3")
            authority = anchor.select_one("p")
            date_nodes = anchor.select("div[aria-labelledby='date'] p, div[aria-labelledby='location'] p")
            if not title or not authority:
                continue
            published_at = self._extract_result_date(date_nodes, "Veröffentlicht")
            if not published_at:
                continue
            result = self._fetch_detail(
                detail_url,
                listing_title=title.get_text(" ", strip=True),
                listing_authority=authority.get_text(" ", strip=True),
                published_at=published_at,
                product_hint=config.product_interest,
            )
            if not result:
                continue
            seen_urls.add(detail_url)
            leads.append(result)
            if len(leads) >= self.max_results:
                break
        return leads

    def _read_search_markup(self, response: requests.Response) -> str:
        chunks: list[str] = []
        with response:
            for index, chunk in enumerate(response.iter_content(self.search_chunk_size)):
                chunks.append(chunk.decode("utf-8", errors="ignore"))
                markup = "".join(chunks)
                if markup.count("IMPORTE/Ausschreibungen/") >= max(self.max_results * 2, 6):
                    return markup
                if index >= 8:
                    break
        return "".join(chunks)

    def _fetch_detail(
        self,
        detail_url: str,
        *,
        listing_title: str,
        listing_authority: str,
        published_at: datetime,
        product_hint: str | None,
    ) -> RawLeadRecord | None:
        try:
            response = requests.get(
                detail_url,
                headers={"User-Agent": self.user_agent},
                timeout=self.page_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        detail_text = soup.get_text("\n", strip=True)
        external_notice_url = self._extract_external_notice_url(soup, base_url=str(response.url))
        buyer_name = self._clean_label_value(listing_authority.replace("Vergabestelle", "", 1)) or self._extract_value_after_label(
            detail_text, "Vergabestelle:"
        )
        demand_summary = self._extract_notice_title(listing_title, detail_text)

        website = self._website_from_url(detail_url)
        buyer_contact_name = None
        contact_email = None
        contact_phone = None
        description = demand_summary

        if external_notice_url:
            external_data = self._fetch_external_notice(external_notice_url)
            if external_data:
                buyer_name = external_data.get("buyer_name") or buyer_name
                website = external_data.get("website") or website
                buyer_contact_name = external_data.get("buyer_contact_name")
                contact_email = external_data.get("contact_email")
                contact_phone = external_data.get("contact_phone")
                description = external_data.get("description") or description

        if buyer_name and not (contact_email or contact_phone):
            enriched = self.contact_enricher.enrich(company_name=buyer_name, country="Germany")
            if enriched:
                website = enriched.website or website
                contact_email = contact_email or enriched.email
                contact_phone = contact_phone or enriched.phone

        if not contact_email and not contact_phone:
            return None

        return RawLeadRecord(
            source_name="service-bund-search",
            company_name=buyer_name or "Germany Public Buyer",
            website=website,
            country="Germany",
            description=description,
            source_url=detail_url,
            contact_hint=external_notice_url or detail_url,
            product_hint=product_hint,
            search_query=listing_title,
            demand_summary=demand_summary,
            demand_posted_at=published_at,
            buyer_contact_name=buyer_contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            demand_type="public_procurement_notice",
        )

    def _fetch_external_notice(self, url: str) -> dict[str, str] | None:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.user_agent},
                timeout=self.page_timeout_seconds,
                allow_redirects=True,
            )
            response.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text("\n", strip=True)
        buyer_name = self._extract_value_after_label(text, "Offizielle Bezeichnung:")
        website = self._extract_value_after_label(text, "Internet-Adresse (URL):")
        buyer_contact_name = self._extract_value_after_label(text, "Kontaktstelle:")
        contact_email = self._extract_value_after_label(text, "E-Mail:")
        contact_phone = self._extract_value_after_label(text, "Telefon:")
        title = self._extract_value_after_label(text, "Titel:")
        description = self._extract_value_after_label(text, "Beschreibung:")

        if not buyer_name and not contact_email and not contact_phone:
            return None
        if contact_phone and (contact_phone.lower().startswith("fax") or len(re.sub(r"\D", "", contact_phone)) < 7):
            contact_phone = None

        return {
            "buyer_name": buyer_name or "",
            "website": website or self._website_from_url(str(response.url)),
            "buyer_contact_name": buyer_contact_name or "",
            "contact_email": contact_email or "",
            "contact_phone": contact_phone or "",
            "description": description or title or "",
        }

    @staticmethod
    def _extract_result_date(nodes, label: str) -> datetime | None:
        for node in nodes:
            text = node.get_text(" ", strip=True)
            if label not in text:
                continue
            parts = re.split(r"\s+", text)
            for token in reversed(parts):
                try:
                    return datetime.strptime(token, "%d.%m.%y")
                except ValueError:
                    continue
        return None

    @staticmethod
    def _extract_value_after_label(text: str, label: str) -> str | None:
        lines = [line.strip() for line in text.splitlines()]
        for index, line in enumerate(lines):
            if not line.startswith(label):
                continue
            remainder = line[len(label):].strip()
            if remainder:
                return ServiceBundNoticeConnector._clean_label_value(remainder)
            for next_line in lines[index + 1 :]:
                if not next_line:
                    continue
                if next_line.endswith(":"):
                    break
                return ServiceBundNoticeConnector._clean_label_value(next_line)
        match = re.search(re.escape(label) + r"\s*(.+)", text)
        if not match:
            return None
        value = match.group(1).splitlines()[0].strip()
        return ServiceBundNoticeConnector._clean_label_value(value)

    @staticmethod
    def _extract_notice_title(listing_title: str, detail_text: str) -> str:
        title = ServiceBundNoticeConnector._extract_value_after_label(detail_text, "Titel:")
        if title:
            return title
        cleaned = re.sub(r"\s+", " ", listing_title).strip()
        return re.sub(r"^Ausschreibung", "", cleaned).strip()

    @staticmethod
    def _extract_external_notice_url(soup: BeautifulSoup, *, base_url: str) -> str | None:
        for anchor in soup.select("a[href]"):
            label = anchor.get_text(" ", strip=True)
            if "Bekanntmachung (HTML-Seite)" not in label:
                continue
            href = anchor.get("href", "").strip()
            if not href:
                continue
            return ServiceBundNoticeConnector._normalize_url(urljoin(base_url, href))
        return None

    @staticmethod
    def _clean_label_value(value: str | None) -> str | None:
        if not value:
            return None
        cleaned = re.sub(r"\s+", " ", value).replace("…", "").strip(" :")
        return cleaned or None

    @staticmethod
    def _normalize_url(url: str | None) -> str | None:
        if not url:
            return None
        cleaned = re.sub(r";jsessionid=[^?]+", "", url)
        parsed = urlparse(cleaned)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))

    @staticmethod
    def _website_from_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
