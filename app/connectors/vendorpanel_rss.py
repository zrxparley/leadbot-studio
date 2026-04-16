import re
from datetime import datetime
from html import unescape
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException, SSLError

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig
from app.services.public_contact_enricher import EnrichedContact, PublicContactEnricher


class VendorPanelRSSConnector:
    rss_url = "https://www.vendorpanel.com.au/PublicTendersRssV2.aspx?mode=all"
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"

    def __init__(
        self,
        *,
        max_results: int = 4,
        timeout_seconds: int = 20,
    ) -> None:
        self.max_results = max_results
        self.timeout_seconds = timeout_seconds
        self.contact_enricher = PublicContactEnricher(timeout_seconds=12)
        self._issuer_cache: dict[str, EnrichedContact | None] = {}

    def fetch(self, config: LeadQueryConfig) -> list[RawLeadRecord]:
        response = self._request(self.rss_url)
        if not response:
            return []

        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError:
            return []

        keywords = self._normalize_keywords(config.query)
        leads: list[RawLeadRecord] = []
        seen_links: set[str] = set()
        for item in root.findall("./channel/item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description_html = item.findtext("description") or ""
            description_text = self._strip_html(description_html)
            haystack = f"{title} {description_text}".lower()
            if not title or not link:
                continue
            if keywords and not self._matches_keywords(haystack, keywords):
                continue
            if link in seen_links:
                continue
            record = self._build_record(
                title=title,
                link=link,
                description_html=description_html,
                description_text=description_text,
                product_hint=config.product_interest,
            )
            if not record:
                continue
            seen_links.add(link)
            leads.append(record)
            if len(leads) >= self.max_results:
                break
        return leads

    def _build_record(
        self,
        *,
        title: str,
        link: str,
        description_html: str,
        description_text: str,
        product_hint: str | None,
    ) -> RawLeadRecord | None:
        issued_by = self._extract_labeled_value(description_html, "Issued by")
        closing_date = self._extract_labeled_value(description_html, "Closing Date")
        reference_number = self._extract_labeled_value(description_html, "Reference number")
        if not issued_by or not closing_date:
            return None

        enriched = self._enrich_issued_by(issued_by)
        if not enriched or not (enriched.email and enriched.phone):
            return None

        demand_posted_at = self._parse_closing_date(closing_date)
        if not demand_posted_at:
            return None

        return RawLeadRecord(
            source_name="vendorpanel-rss",
            company_name=issued_by,
            website=enriched.website,
            country="Australia",
            description=description_text or title,
            source_url=link,
            contact_hint=enriched.contact_source_url,
            product_hint=product_hint,
            search_query=reference_number or title,
            demand_summary=title,
            demand_posted_at=demand_posted_at,
            buyer_contact_name=None,
            contact_email=enriched.email,
            contact_phone=enriched.phone,
            demand_type="public_procurement_notice",
        )

    @staticmethod
    def _extract_labeled_value(description_html: str, label: str) -> str:
        html = unescape(description_html)
        pattern = re.compile(
            rf"<b>\s*{re.escape(label)}\s*:?\s*</b>\s*(.*?)(?:<br\s*/?>|$)",
            flags=re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(html)
        if not match:
            return ""
        fragment = match.group(1).strip()
        if "<" in fragment or "&" in fragment:
            value = BeautifulSoup(fragment, "html.parser").get_text(" ", strip=True)
        else:
            value = fragment
        return re.sub(r"\s+", " ", value).strip(" .:")

    @staticmethod
    def _strip_html(value: str | None) -> str:
        if not value:
            return ""
        return BeautifulSoup(unescape(value), "html.parser").get_text(" ", strip=True)

    @staticmethod
    def _parse_closing_date(value: str) -> datetime | None:
        cleaned = re.sub(r"\s*\(UTC[^)]*\).*", "", value).strip()
        for fmt in ("%d/%b/%Y %I:%M %p", "%d/%b/%Y %H:%M", "%d/%m/%Y %I:%M %p"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_keywords(query: str) -> list[str]:
        tokens = re.split(r"[,\s]+", query.lower())
        return [token for token in tokens if len(token) >= 4]

    @staticmethod
    def _matches_keywords(haystack: str, keywords: list[str]) -> bool:
        return any(re.search(rf"\b{re.escape(keyword)}\b", haystack) for keyword in keywords)

    def _enrich_issued_by(self, company_name: str) -> EnrichedContact | None:
        cache_key = company_name.strip().lower()
        if cache_key in self._issuer_cache:
            return self._issuer_cache[cache_key]

        best_match: EnrichedContact | None = None
        best_score = -1
        queries = [
            f'"{company_name}" Australia contact',
            f"{company_name} Australia contact",
        ]
        for query in queries:
            for result in self.contact_enricher._search(query)[:3]:
                enriched = self.contact_enricher._extract_from_page(
                    result["url"],
                    country="Australia",
                )
                if not enriched or not (enriched.email and enriched.phone):
                    continue
                score = self.contact_enricher._contact_score(enriched)
                if score > best_score:
                    best_match = enriched
                    best_score = score
        self._issuer_cache[cache_key] = best_match
        return best_match

    def _request(self, url: str) -> requests.Response | None:
        kwargs = {
            "timeout": self.timeout_seconds,
            "headers": {"User-Agent": self.user_agent},
            "allow_redirects": True,
        }
        try:
            response = requests.get(url, **kwargs)
            response.raise_for_status()
            return response
        except SSLError:
            try:
                response = requests.get(url, verify=False, **kwargs)
                response.raise_for_status()
                return response
            except RequestException:
                return None
        except RequestException:
            return None
