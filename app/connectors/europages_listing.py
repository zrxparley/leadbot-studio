from collections import OrderedDict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig


class EuropagesListingConnector:
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"

    def __init__(self, *, listing_timeout_seconds: int = 15, page_timeout_seconds: int = 10) -> None:
        self.listing_timeout_seconds = listing_timeout_seconds
        self.page_timeout_seconds = page_timeout_seconds

    def fetch(self, config: LeadQueryConfig, max_results: int) -> list[RawLeadRecord]:
        if not config.url:
            return []

        response = requests.get(
            config.url,
            timeout=self.listing_timeout_seconds,
            headers={"User-Agent": self.user_agent},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        company_links = self._extract_company_links(soup, base_url=str(response.url))
        leads: list[RawLeadRecord] = []
        for company_name, company_url in company_links[:max_results]:
            description, website, contact_hint = self._fetch_company_profile(company_url)
            leads.append(
                RawLeadRecord(
                    source_name=f"europages:{config.name}",
                    company_name=company_name,
                    website=website or company_url,
                    country=config.country,
                    description=description or config.query,
                    source_url=company_url,
                    contact_hint=contact_hint or website or company_url,
                    product_hint=config.product_interest,
                    search_query=config.query,
                )
            )
        return leads

    def _extract_company_links(self, soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
        links: "OrderedDict[str, str]" = OrderedDict()
        for anchor in soup.select('a[href*="/en/company/"]'):
            href = anchor.get("href", "").strip()
            text = anchor.get_text(" ", strip=True)
            if not href or not text:
                continue
            if "/products/" in href or text.lower().startswith("view portfolio"):
                continue
            full_url = urljoin(base_url, href)
            if full_url in links:
                continue
            links[full_url] = text
        return [(name, url) for url, name in links.items()]

    def _fetch_company_profile(self, url: str) -> tuple[str, str | None, str | None]:
        try:
            response = requests.get(
                url,
                timeout=self.page_timeout_seconds,
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()
        except requests.RequestException:
            return "", None, None

        soup = BeautifulSoup(response.text, "html.parser")
        description = ""
        description_meta = soup.find("meta", attrs={"name": "description"})
        if description_meta and description_meta.get("content"):
            description = description_meta["content"].strip()
        if not description:
            about_heading = soup.find("h2", string=lambda value: value and value.strip().startswith("About "))
            if about_heading:
                next_text = about_heading.find_next(string=True)
                if next_text:
                    description = next_text.strip()

        website = None
        contact_hint = None
        for anchor in soup.select("a[href]"):
            text = anchor.get_text(" ", strip=True)
            href = anchor.get("href", "").strip()
            if text == "Company's Website" and href:
                website = href
                contact_hint = href
                break
            if href.startswith("mailto:") or href.startswith("tel:"):
                contact_hint = href
        return description, website, contact_hint
