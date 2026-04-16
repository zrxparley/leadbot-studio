import re

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig


class EnvironmentalExpertListingConnector:
    country_aliases = {
        "UAE": "United Arab Emirates",
        "UK": "United Kingdom",
        "U.S.A.": "United States",
        "USA": "United States",
    }

    def __init__(
        self,
        *,
        listing_timeout_seconds: int = 15,
        browser_wait_milliseconds: int = 5000,
    ) -> None:
        self.listing_timeout_seconds = listing_timeout_seconds
        self.browser_wait_milliseconds = browser_wait_milliseconds

    def fetch(self, config: LeadQueryConfig, max_results: int) -> list[RawLeadRecord]:
        if not config.url:
            return []

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return []

        cards: list[dict[str, str]] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(
                    config.url,
                    wait_until="domcontentloaded",
                    timeout=self._navigation_timeout_milliseconds(),
                )
                page.wait_for_timeout(self.browser_wait_milliseconds)
                try:
                    page.wait_for_load_state(
                        "networkidle",
                        timeout=min(self.browser_wait_milliseconds, 5000),
                    )
                except Exception:
                    pass
                cards = page.evaluate(
                    """
                    () => {
                      const companyPattern = /^\\/companies\\/[^/]+-\\d+$/;
                      const seen = new Set();
                      const results = [];

                      for (const anchor of document.querySelectorAll('a[href]')) {
                        const rawHref = anchor.getAttribute('href') || '';
                        const companyName = (anchor.textContent || '').trim();
                        if (!companyName || companyName.toUpperCase() === 'CONTACT SUPPLIER') {
                          continue;
                        }

                        const absoluteHref = new URL(rawHref, window.location.href).toString();
                        const pathname = new URL(absoluteHref).pathname;
                        const slug = pathname.split('/').pop() || '';
                        if (!companyPattern.test(pathname) || seen.has(absoluteHref)) {
                          continue;
                        }
                        if (
                          slug.startsWith('keyword-') ||
                          slug.startsWith('location-') ||
                          slug.startsWith('industry-') ||
                          slug.startsWith('business-type-') ||
                          slug.startsWith('employees-')
                        ) {
                          continue;
                        }

                        let cardText = companyName;
                        let node = anchor;
                        while (node && node !== document.body) {
                          const candidateText = (node.innerText || '').trim();
                          if (candidateText.length > 120 && candidateText.length < 2500) {
                            cardText = candidateText;
                            break;
                          }
                          node = node.parentElement;
                        }

                        seen.add(absoluteHref);
                        results.push({
                          companyName,
                          href: absoluteHref,
                          cardText,
                        });
                      }

                      return results;
                    }
                    """
                )
            finally:
                browser.close()

        local_records: list[RawLeadRecord] = []
        remote_records: list[RawLeadRecord] = []
        for card in cards:
            company_name = card.get("companyName", "").strip()
            source_url = card.get("href", "").strip()
            card_text = card.get("cardText", "")
            if not company_name or not source_url:
                continue

            based_in = self._extract_based_in(card_text)
            normalized_country = self._normalize_country(based_in)
            country = normalized_country or (config.country if based_in else "Unknown")
            description = self._extract_description(card_text, company_name)

            record = RawLeadRecord(
                source_name=f"environmental-expert:{config.name}",
                company_name=company_name,
                website=source_url,
                country=country,
                description=description or config.query,
                source_url=source_url,
                contact_hint=source_url,
                product_hint=config.product_interest,
                search_query=config.query,
            )
            if country.lower() == config.country.lower():
                local_records.append(record)
            else:
                remote_records.append(record)

        return (local_records + remote_records)[:max_results]

    def _navigation_timeout_milliseconds(self) -> int:
        return max(self.listing_timeout_seconds, 30) * 1000

    def _extract_based_in(self, card_text: str) -> str | None:
        match = re.search(r"based in\s*(.+)", card_text, flags=re.IGNORECASE)
        if not match:
            return None
        return re.sub(r"\s+", " ", match.group(1).splitlines()[0]).strip()

    def _normalize_country(self, based_in: str | None) -> str | None:
        if not based_in:
            return None

        paren_match = re.search(r"\(([^)]+)\)", based_in)
        if paren_match:
            alias = paren_match.group(1).strip().upper()
            if alias in self.country_aliases:
                return self.country_aliases[alias]

        last_part = based_in.rsplit(",", maxsplit=1)[-1].strip().upper()
        if last_part in self.country_aliases:
            return self.country_aliases[last_part]
        if last_part and last_part == last_part.upper():
            return last_part.title()
        return None

    def _extract_description(self, card_text: str, company_name: str) -> str:
        lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in card_text.splitlines()
            if line.strip()
        ]
        description_lines: list[str] = []
        for line in lines:
            lowered = line.lower()
            if lowered in {"premium", "contact supplier"}:
                continue
            if lowered.startswith("based in"):
                continue
            if line == company_name:
                continue
            description_lines.append(line)
        return " ".join(description_lines[:3])
