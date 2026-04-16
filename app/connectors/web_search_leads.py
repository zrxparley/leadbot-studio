from dataclasses import dataclass
import re
from typing import Iterable
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.utils import requote_uri

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class DuckDuckGoLeadConnector:
    search_endpoint = "https://html.duckduckgo.com/html/"
    user_agent = "MarketInsightOfficer/0.1 (+https://local.dev)"
    ignored_domains = {
        "duckduckgo.com",
        "google.com",
        "www.google.com",
        "news.google.com",
        "youtube.com",
        "www.youtube.com",
        "facebook.com",
        "www.facebook.com",
        "instagram.com",
        "www.instagram.com",
        "linkedin.com",
        "www.linkedin.com",
        "x.com",
        "twitter.com",
        "wikipedia.org",
    }
    content_markers = {
        "market",
        "report",
        "forecast",
        "top 10",
        "top 20",
        "top 30",
        "news",
        "press release",
        "insights",
        "blog",
        "article",
        "analysis",
    }

    def __init__(
        self,
        max_results: int = 5,
        *,
        search_timeout_seconds: int = 15,
        page_timeout_seconds: int = 10,
    ) -> None:
        self.max_results = max_results
        self.search_timeout_seconds = search_timeout_seconds
        self.page_timeout_seconds = page_timeout_seconds

    def fetch(self, config: LeadQueryConfig) -> list[RawLeadRecord]:
        response = requests.get(
            self.search_endpoint,
            params={"q": config.query},
            timeout=self.search_timeout_seconds,
            headers={"User-Agent": self.user_agent},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        leads: list[RawLeadRecord] = []
        for result in self._parse_results(soup):
            if len(leads) >= self.max_results:
                break
            normalized_url = self._normalize_result_url(result.url)
            if not normalized_url or not self._is_candidate_url(normalized_url):
                continue
            if not self._matches_allowed_domains(normalized_url, config.allowed_domains):
                continue
            if self._looks_like_directory_listing(result.title, result.snippet, normalized_url):
                continue
            if self._looks_like_content_page(result.title, result.snippet, normalized_url):
                continue

            page_title, page_description, contact_hint = self._fetch_company_page(normalized_url)
            if self._looks_like_content_page(page_title, page_description, normalized_url):
                continue
            description = page_description or result.snippet or result.title
            company_name = self._guess_company_name(page_title or result.title, normalized_url)
            website = self._website_from_url(normalized_url)

            leads.append(
                RawLeadRecord(
                    source_name=f"duckduckgo:{config.name}",
                    company_name=company_name,
                    website=website,
                    country=config.country,
                    description=description,
                    source_url=normalized_url,
                    contact_hint=contact_hint or website,
                    product_hint=config.product_interest,
                    search_query=config.query,
                )
            )

        return leads

    def _parse_results(self, soup: BeautifulSoup) -> Iterable[SearchResult]:
        for result in soup.select(".result"):
            title_link = result.select_one(".result__title a.result__a") or result.select_one("a.result__a")
            if not title_link:
                continue
            snippet_node = result.select_one(".result__snippet")
            yield SearchResult(
                title=title_link.get_text(" ", strip=True),
                url=title_link.get("href", "").strip(),
                snippet=snippet_node.get_text(" ", strip=True) if snippet_node else "",
            )

    def _fetch_company_page(self, url: str) -> tuple[str, str, str | None]:
        try:
            response = requests.get(
                url,
                timeout=self.page_timeout_seconds,
                headers={"User-Agent": self.user_agent},
                allow_redirects=True,
            )
            response.raise_for_status()
        except requests.RequestException:
            return "", "", None

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""

        meta_description = ""
        description_tag = soup.find("meta", attrs={"name": "description"})
        if description_tag and description_tag.get("content"):
            meta_description = description_tag["content"].strip()
        if not meta_description:
            og_description = soup.find("meta", attrs={"property": "og:description"})
            if og_description and og_description.get("content"):
                meta_description = og_description["content"].strip()

        contact_hint = None
        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            if href.startswith("mailto:") or href.startswith("tel:"):
                contact_hint = href
                break
            if "contact" in href.lower():
                contact_hint = urljoin(str(response.url), href)
                break

        return title, meta_description, contact_hint

    def _normalize_result_url(self, url: str) -> str:
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

    def _is_candidate_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if host in self.ignored_domains:
            return False
        if parsed.path.lower().endswith((".pdf", ".jpg", ".png")):
            return False
        return True

    @staticmethod
    def _matches_allowed_domains(url: str, allowed_domains: list[str] | None) -> bool:
        if not allowed_domains:
            return True
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        normalized_allowed = {
            domain.lower()[4:] if domain.lower().startswith("www.") else domain.lower()
            for domain in allowed_domains
        }
        return any(host == domain or host.endswith(f".{domain}") for domain in normalized_allowed)

    @staticmethod
    def _looks_like_directory_listing(title: str, snippet: str, url: str) -> bool:
        haystack = f"{title} {snippet} {url}".lower()
        listing_markers = [
            "companies and suppliers",
            "find wholesalers",
            "b2b marketplace",
            "/companies/",
            "company directory",
        ]
        return any(marker in haystack for marker in listing_markers)

    def _looks_like_content_page(self, title: str, snippet: str, url: str) -> bool:
        haystack = f"{title} {snippet} {url}".lower()
        if any(marker in haystack for marker in self.content_markers):
            return True
        if re.search(r"\btop\s+\d+\b", haystack):
            return True
        noisy_paths = ["/news/", "/blog/", "/insights/", "/article/", "/articles/"]
        return any(path in haystack for path in noisy_paths)

    @staticmethod
    def _website_from_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _guess_company_name(title: str, url: str) -> str:
        cleaned = title.split(" - ")[0].split(" | ")[0].strip()
        if cleaned:
            return cleaned[:255]
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
