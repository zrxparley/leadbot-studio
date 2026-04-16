import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup
from requests.utils import requote_uri

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig
from app.services.public_contact_enricher import PublicContactEnricher


@dataclass(slots=True)
class NoticeSearchResult:
    title: str
    url: str
    snippet: str


class UNGMNoticeConnector:
    search_endpoint = "https://html.duckduckgo.com/html/"
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"
    email_pattern = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
    phone_pattern = re.compile(r"\+?\d[\d\s()./-]{7,}\d")

    def __init__(
        self,
        *,
        max_results: int = 3,
        search_timeout_seconds: int = 15,
        page_timeout_seconds: int = 12,
    ) -> None:
        self.max_results = max_results
        self.search_timeout_seconds = search_timeout_seconds
        self.page_timeout_seconds = page_timeout_seconds
        self.contact_enricher = PublicContactEnricher(timeout_seconds=page_timeout_seconds)

    def fetch(self, config: LeadQueryConfig) -> list[RawLeadRecord]:
        if config.url:
            notice = self._fetch_notice(config.url, product_hint=config.product_interest)
            return [notice] if notice else []

        response = requests.get(
            self.search_endpoint,
            params={"q": config.query},
            timeout=self.search_timeout_seconds,
            headers={"User-Agent": self.user_agent},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        leads: list[RawLeadRecord] = []
        seen_urls: set[str] = set()
        for result in self._parse_results(soup):
            if len(leads) >= self.max_results:
                break
            normalized_url = self._normalize_result_url(result.url)
            if not normalized_url or normalized_url in seen_urls:
                continue
            if not self._is_notice_url(normalized_url):
                continue
            notice = self._fetch_notice(normalized_url, product_hint=config.product_interest)
            if not notice:
                continue
            seen_urls.add(normalized_url)
            leads.append(notice)
        return leads

    def _parse_results(self, soup: BeautifulSoup) -> list[NoticeSearchResult]:
        results: list[NoticeSearchResult] = []
        for result in soup.select(".result"):
            title_link = result.select_one(".result__title a.result__a") or result.select_one("a.result__a")
            if not title_link:
                continue
            snippet_node = result.select_one(".result__snippet")
            results.append(
                NoticeSearchResult(
                    title=title_link.get_text(" ", strip=True),
                    url=title_link.get("href", "").strip(),
                    snippet=snippet_node.get_text(" ", strip=True) if snippet_node else "",
                )
            )
        return results

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
        title = soup.select_one("h1")
        notice_title = title.get_text(" ", strip=True) if title else ""
        text = soup.get_text("\n", strip=True)

        published_at = self._extract_date_after_label(text, "Published on:")
        if not published_at:
            return None
        country = self._extract_value_after_label(text, "Beneficiary countries or territories:") or "Global"
        country = self._normalize_country(country)
        description = self._extract_value_after_label(text, "Description") or notice_title
        organization = self._extract_organization(description=description, country=country, text=text)
        contact_email = self._extract_contact_email(text) or self._extract_best_email(text)
        contact_phone = self._extract_contact_phone(text) or self._extract_best_phone(text)
        buyer_contact_name = self._extract_contact_name(text)

        enriched = None
        if organization and not (contact_email or contact_phone):
            try:
                enriched = self.contact_enricher.enrich(company_name=organization, country=country)
            except Exception:
                enriched = None

        enrichment_filled_gap = False
        if enriched:
            if not contact_email and enriched.email:
                contact_email = enriched.email
                enrichment_filled_gap = True
            if not contact_phone and enriched.phone:
                contact_phone = enriched.phone
                enrichment_filled_gap = True

        if not contact_email and not contact_phone:
            return None

        website = enriched.website if enriched else self._website_from_url(url)
        contact_hint = enriched.contact_source_url if enrichment_filled_gap else url
        company_name = organization or country

        demand_summary = self._clean_summary(description)
        return RawLeadRecord(
            source_name="ungm-notice-search",
            company_name=company_name,
            website=website,
            country=country,
            description=demand_summary,
            source_url=str(response.url),
            contact_hint=contact_hint,
            product_hint=product_hint,
            search_query=notice_title,
            demand_summary=demand_summary,
            demand_posted_at=published_at,
            buyer_contact_name=buyer_contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            demand_type="public_procurement_notice",
        )

    @staticmethod
    def _extract_value_after_label(text: str, label: str) -> str | None:
        if label == "Description":
            match = re.search(
                r"Description\s+(.*?)\s+(?:Documents|Contacts|UNSPSC codes|Similar notices)",
                text,
                flags=re.DOTALL,
            )
            if match:
                return re.sub(r"\s+", " ", match.group(1)).strip()
            return None

        pattern = re.escape(label) + r"\s*(.+)"
        match = re.search(pattern, text)
        if not match:
            return None
        value = match.group(1).splitlines()[0].strip()
        return re.sub(r"\s+", " ", value)

    @staticmethod
    def _extract_date_after_label(text: str, label: str) -> datetime | None:
        value = UNGMNoticeConnector._extract_value_after_label(text, label)
        if not value:
            return None
        try:
            return datetime.strptime(value, "%d-%b-%Y")
        except ValueError:
            return None

    def _extract_organization(self, *, description: str, country: str, text: str) -> str | None:
        delivered_match = re.search(
            r"to be delivered to\s+([A-Z][A-Za-z0-9 .,&()-]+?)(?:\s+If you are|\.\s|$)",
            description,
            flags=re.IGNORECASE,
        )
        if delivered_match:
            return delivered_match.group(1).strip()

        invite_match = re.search(
            r"The\s+([A-Z][A-Za-z0-9 .,&()-]+?)\s+\(([A-Z]{2,10})\)\s+invites you",
            description,
        )
        if invite_match:
            acronym = invite_match.group(2).strip()
            if country and country != "Global":
                return f"{acronym} {country}"
            return acronym

        email = self._extract_best_email(text)
        if email:
            domain = email.split("@")[-1].lower()
            if domain.endswith("fao.org") and country and country != "Global":
                return f"FAO {country}"
            root = domain.split(".")[0].upper()
            if country and country not in {"Global", "Multiple destinations"}:
                return f"{root} {country}"
            return root

        return None

    @staticmethod
    def _extract_contact_name(text: str) -> str | None:
        full_name = UNGMNoticeConnector._extract_value_after_label(text, "Contact person:")
        if full_name:
            return full_name
        first_name = UNGMNoticeConnector._extract_value_after_label(text, "First name:")
        surname = UNGMNoticeConnector._extract_value_after_label(text, "Surname:")
        if first_name and surname:
            return f"{first_name} {surname}"
        return None

    @staticmethod
    def _extract_contact_email(text: str) -> str | None:
        return UNGMNoticeConnector._extract_value_after_label(text, "Email address:")

    @staticmethod
    def _extract_contact_phone(text: str) -> str | None:
        country_code = UNGMNoticeConnector._extract_value_after_label(text, "Telephone country code:")
        number = UNGMNoticeConnector._extract_value_after_label(text, "Telephone number:")
        if not number:
            return None
        digits = re.sub(r"\D", "", number)
        if not digits:
            return None
        if country_code:
            code_match = re.search(r"\((\+\d+)\)", country_code)
            if code_match:
                return f"{code_match.group(1)} {digits}"
        return digits

    def _extract_best_email(self, text: str) -> str | None:
        emails = sorted(set(self.email_pattern.findall(text)))
        preferred = [
            email
            for email in emails
            if not any(marker in email.lower() for marker in {"ungm", "no-reply", "noreply"})
        ]
        candidates = preferred or emails
        return candidates[0] if candidates else None

    def _extract_best_phone(self, text: str) -> str | None:
        phones = []
        for phone in sorted(set(self.phone_pattern.findall(text))):
            digits = re.sub(r"\D", "", phone)
            if len(digits) < 8:
                continue
            if re.fullmatch(r"\d{8}", digits):
                continue
            phones.append(re.sub(r"\s+", " ", phone).strip())
        return phones[0] if phones else None

    @staticmethod
    def _clean_summary(description: str) -> str:
        cleaned = re.sub(r"\s+", " ", description).strip()
        return cleaned[:800]

    @staticmethod
    def _normalize_country(country: str) -> str:
        cleaned = re.sub(r"\s+", " ", country).strip()
        if cleaned.lower().startswith("multiple destinations"):
            return "Multiple destinations"
        return cleaned

    @staticmethod
    def _is_notice_url(url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        return "ungm.org" in host and "/Public/Notice/" in parsed.path

    @staticmethod
    def _normalize_result_url(url: str) -> str:
        if not url:
            return ""
        if url.startswith("//"):
            url = f"https:{url}"
        parsed = urlparse(url)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            query = parse_qs(parsed.query)
            uddg = query.get("uddg")
            if uddg:
                return requote_uri(unquote(uddg[0]))
        return requote_uri(url)

    @staticmethod
    def _website_from_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
