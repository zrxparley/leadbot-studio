import re
from datetime import datetime, timedelta

from app.connectors.base import RawLeadRecord
from app.connectors.lead_registry import LeadQueryConfig
from app.services.public_contact_enricher import PublicContactEnricher


class Go4WorldBusinessBuyerConnector:
    country_aliases = {
        "Viet Nam": "Vietnam",
        "United States Of America": "United States",
        "U.A.E.": "United Arab Emirates",
    }

    def __init__(
        self,
        *,
        listing_timeout_seconds: int = 15,
        browser_wait_milliseconds: int = 5000,
        contact_timeout_seconds: int = 12,
        max_age_days: int = 365,
    ) -> None:
        self.listing_timeout_seconds = listing_timeout_seconds
        self.browser_wait_milliseconds = browser_wait_milliseconds
        self.max_age_days = max_age_days
        self.contact_enricher = PublicContactEnricher(timeout_seconds=contact_timeout_seconds)

    def fetch(
        self,
        config: LeadQueryConfig,
        max_results: int,
        *,
        as_of: datetime | None = None,
    ) -> list[RawLeadRecord]:
        if not config.url:
            return []
        cutoff = (as_of or datetime.now()) - timedelta(days=self.max_age_days)

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
                    timeout=max(self.listing_timeout_seconds, 45) * 1000,
                )
                page.wait_for_timeout(self.browser_wait_milliseconds)
                try:
                    page.wait_for_load_state(
                        "networkidle",
                        timeout=min(self.browser_wait_milliseconds, 5000),
                    )
                except Exception:
                    pass
                cards = self._extract_cards(page)
            finally:
                browser.close()

        leads: list[RawLeadRecord] = []
        candidate_cards = cards[: max(max_results * 3, max_results)]
        for card in candidate_cards:
            company_name = card.get("companyName", "").strip()
            source_url = card.get("href", "").strip()
            card_text = card.get("cardText", "")
            if not company_name or not source_url:
                continue

            country = self._extract_country(card_text) or config.country
            demand_posted_at = self._extract_demand_posted_at(card_text)
            if not demand_posted_at or demand_posted_at < cutoff:
                continue
            demand_summary = self._extract_demand_summary(card_text, company_name)
            enriched = self.contact_enricher.enrich(company_name=company_name, country=country)
            if not enriched or not (enriched.email or enriched.phone):
                continue

            leads.append(
                RawLeadRecord(
                    source_name=f"go4worldbusiness-buyer:{config.name}",
                    company_name=company_name,
                    website=enriched.website or source_url,
                    country=country,
                    description=demand_summary or config.query,
                    source_url=source_url,
                    contact_hint=enriched.contact_source_url,
                    product_hint=config.product_interest,
                    search_query=config.query,
                    demand_summary=demand_summary or config.query,
                    demand_posted_at=demand_posted_at,
                    contact_email=enriched.email,
                    contact_phone=enriched.phone,
                    demand_type="recent_buyer_requirement",
                )
            )
            if len(leads) >= max_results:
                break

        return leads

    def _extract_cards(self, page) -> list[dict[str, str]]:
        script = """
        () => {
          const results = [];
          const seen = new Set();

          for (const anchor of document.querySelectorAll('a[href]')) {
            const rawHref = anchor.getAttribute('href') || '';
            const companyName = (anchor.textContent || '').trim();
            if (!rawHref.includes('/member/view/') || !companyName) {
              continue;
            }

            const absoluteHref = new URL(rawHref, window.location.href).toString();
            if (seen.has(absoluteHref)) {
              continue;
            }

            let cardText = companyName;
            let node = anchor;
            while (node && node !== document.body) {
              const candidateText = (node.innerText || '').trim();
              if (
                candidateText.includes('Buyer From') &&
                candidateText.length > 120 &&
                candidateText.length < 2500
              ) {
                cardText = candidateText;
                break;
              }
              node = node.parentElement;
            }

            if (!cardText.includes('Buyer From')) {
              continue;
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
        for _ in range(3):
            try:
                return page.evaluate(script)
            except Exception as exc:
                if "Execution context was destroyed" not in str(exc):
                    raise
                page.wait_for_timeout(3000)
        return []

    def _extract_country(self, card_text: str) -> str | None:
        match = re.search(r"Buyer From\s+(.+)", card_text, flags=re.IGNORECASE)
        if not match:
            return None
        location = re.sub(r"\s+", " ", match.group(1).splitlines()[0]).strip()
        country = None
        if "," in location:
            country = location.rsplit(",", maxsplit=1)[-1].strip().title()
        else:
            country = location.title()
        return self.country_aliases.get(country, country)

    @staticmethod
    def _extract_demand_posted_at(card_text: str) -> datetime | None:
        match = re.search(r"\b([A-Z][a-z]{2}-\d{2}-\d{2})\b", card_text)
        if not match:
            return None
        try:
            return datetime.strptime(match.group(1), "%b-%d-%y")
        except ValueError:
            return None

    def _extract_demand_summary(self, card_text: str, company_name: str) -> str:
        lines = [
            re.sub(r"\s+", " ", line).strip()
            for line in card_text.splitlines()
            if line.strip()
        ]
        demand_lines: list[str] = []
        for line in lines:
            lowered = line.lower()
            if line == company_name:
                continue
            if re.fullmatch(r"[A-Z][a-z]{2}-\d{2}-\d{2}", line):
                continue
            if lowered.startswith("buyer from"):
                continue
            if lowered.startswith("buyer of"):
                continue
            if lowered == "inquire now":
                continue
            demand_lines.append(line)
        return " ".join(demand_lines[:3])
