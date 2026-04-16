from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.go4worldbusiness_buyers import Go4WorldBusinessBuyerConnector
from app.connectors.easytenders_notice import EasyTendersNoticeConnector
from app.connectors.easytenders_search import EasyTendersSearchConnector
from app.connectors.canadabuys_notice import CanadaBuysNoticeConnector
from app.connectors.merx_notice import MerxNoticeConnector
from app.connectors.merx_search import MerxSearchConnector
from app.connectors.service_bund_search import ServiceBundNoticeConnector
from app.connectors.tasmania_tenders_listing import TasmaniaTendersListingConnector
from app.connectors.tenders_wa_listing import TendersWAListingConnector
from app.connectors.vendorpanel_rss import VendorPanelRSSConnector
from app.connectors.ungm_notice_search import UNGMNoticeConnector
from app.connectors.environmental_expert_listing import EnvironmentalExpertListingConnector
from app.connectors.europages_listing import EuropagesListingConnector
from app.connectors.lead_registry import load_lead_queries
from app.connectors.mock_sources import MockLeadConnector
from app.connectors.web_search_leads import DuckDuckGoLeadConnector
from app.core.config import get_settings
from app.db.models import Lead
from app.services.lead_archive import LeadArchiveWriter
from app.services.lead_deduper import LeadDeduper
from app.services.classifier import LeadClassifier
from app.services.scorer import LeadScorer


class LeadGenerationSkill:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.fallback_connector = MockLeadConnector()
        self.settings = get_settings()
        self.go4worldbusiness_buyer_connector = Go4WorldBusinessBuyerConnector(
            listing_timeout_seconds=self.settings.lead_search_timeout_seconds,
            browser_wait_milliseconds=self.settings.lead_browser_wait_milliseconds,
            contact_timeout_seconds=self.settings.lead_page_timeout_seconds + 4,
            max_age_days=self.settings.lead_max_age_days,
        )
        self.ungm_notice_connector = UNGMNoticeConnector(
            max_results=self.settings.lead_search_max_results,
            search_timeout_seconds=self.settings.lead_search_timeout_seconds,
            page_timeout_seconds=self.settings.lead_page_timeout_seconds + 4,
        )
        self.easytenders_notice_connector = EasyTendersNoticeConnector(
            page_timeout_seconds=self.settings.lead_page_timeout_seconds + 4,
        )
        self.canadabuys_notice_connector = CanadaBuysNoticeConnector(
            page_timeout_seconds=self.settings.lead_page_timeout_seconds + 8,
        )
        self.merx_notice_connector = MerxNoticeConnector(
            page_timeout_seconds=self.settings.lead_page_timeout_seconds + 8,
        )
        self.merx_search_connector = MerxSearchConnector(
            max_results=self.settings.lead_search_max_results,
            search_timeout_seconds=self.settings.lead_search_timeout_seconds + 4,
            page_timeout_seconds=self.settings.lead_page_timeout_seconds + 8,
        )
        self.easytenders_search_connector = EasyTendersSearchConnector(
            max_results=self.settings.lead_search_max_results + 2,
            search_timeout_seconds=self.settings.lead_search_timeout_seconds,
            page_timeout_seconds=self.settings.lead_page_timeout_seconds + 4,
        )
        self.service_bund_connector = ServiceBundNoticeConnector(
            max_results=self.settings.lead_search_max_results,
            search_timeout_seconds=self.settings.lead_search_timeout_seconds + 6,
            page_timeout_seconds=self.settings.lead_page_timeout_seconds + 8,
        )
        self.tenders_wa_connector = TendersWAListingConnector(
            max_results=self.settings.lead_search_max_results,
            listing_timeout_seconds=self.settings.lead_search_timeout_seconds + 4,
            page_timeout_seconds=self.settings.lead_page_timeout_seconds + 6,
        )
        self.tasmania_tenders_connector = TasmaniaTendersListingConnector(
            max_results=self.settings.lead_search_max_results,
            listing_timeout_seconds=self.settings.lead_search_timeout_seconds + 4,
            page_timeout_seconds=self.settings.lead_page_timeout_seconds + 6,
        )
        self.vendorpanel_rss_connector = VendorPanelRSSConnector(
            max_results=self.settings.lead_search_max_results,
            timeout_seconds=self.settings.lead_search_timeout_seconds + 6,
        )
        self.europages_connector = EuropagesListingConnector(
            listing_timeout_seconds=self.settings.lead_search_timeout_seconds,
            page_timeout_seconds=self.settings.lead_page_timeout_seconds,
        )
        self.environmental_expert_connector = EnvironmentalExpertListingConnector(
            listing_timeout_seconds=self.settings.lead_search_timeout_seconds,
            browser_wait_milliseconds=self.settings.lead_browser_wait_milliseconds,
        )
        self.search_connector = DuckDuckGoLeadConnector(
            max_results=self.settings.lead_search_max_results,
            search_timeout_seconds=self.settings.lead_search_timeout_seconds,
            page_timeout_seconds=self.settings.lead_page_timeout_seconds,
        )
        self.classifier = LeadClassifier()
        self.scorer = LeadScorer()
        self.archive_writer = LeadArchiveWriter(self.settings.lead_archive_root)
        self.last_archive_path: str | None = None
        self.last_run_stats: dict[str, int] = {}
        self._fetch_duplicates_skipped = 0

    def run(self, as_of: datetime, *, run_name: str = "lead_generation") -> list[Lead]:
        leads: list[Lead] = []
        duplicates_skipped = 0
        self._fetch_duplicates_skipped = 0
        existing_leads = self.db.scalars(select(Lead)).all()
        deduper = LeadDeduper(existing_leads)
        appended_existing_ids: set[int] = set()
        freshness_cutoff = as_of - timedelta(days=self.settings.lead_max_age_days)
        for raw_lead in self._fetch_raw_leads(as_of=as_of):
            if deduper.is_duplicate_in_run(raw_lead):
                duplicates_skipped += 1
                continue

            existing = deduper.find_existing(raw_lead)
            if existing:
                self._refresh_existing_lead(existing, raw_lead=raw_lead, as_of=as_of)
                deduper.register_lead(existing)
                deduper.register_raw(raw_lead)
                if existing.id not in appended_existing_ids:
                    leads.append(existing)
                    appended_existing_ids.add(existing.id)
                else:
                    duplicates_skipped += 1
                continue
            lead_text = "\n".join(
                [
                    raw_lead.description,
                    raw_lead.demand_summary or "",
                    raw_lead.contact_email or "",
                    raw_lead.contact_phone or "",
                ]
            )
            industry = self.classifier.classify_industry(lead_text)
            product_interest = self._resolve_product_interest(lead_text, raw_lead.product_hint)
            role_assessment = self.classifier.assess_company_role(
                company_name=raw_lead.company_name,
                description=lead_text,
                source_url=raw_lead.source_url,
                search_query=raw_lead.search_query,
            )
            status, role_reason = self._resolve_status(
                raw_lead=raw_lead,
                role=role_assessment.role,
                reason=role_assessment.reason,
            )
            lowered_desc = lead_text.lower()
            keyword_match_count = sum(
                1 for keyword in self.settings.lead_target_keywords if keyword.lower() in lowered_desc
            )
            score = self.scorer.score(
                country_match=raw_lead.country in self.settings.lead_target_countries,
                keyword_match_count=keyword_match_count,
                industry_match="filtration" in industry or "screen" in industry,
                has_contact_hint=bool(raw_lead.contact_hint or raw_lead.website),
                has_direct_contact=bool(raw_lead.contact_email or raw_lead.contact_phone),
                website_depth=bool(
                    raw_lead.source_url and raw_lead.website and raw_lead.source_url != raw_lead.website
                ),
                role=status,
                buyer_signal_count=role_assessment.buyer_signal_count,
                supplier_signal_count=role_assessment.supplier_signal_count,
                channel_signal_count=role_assessment.channel_signal_count,
            )
            lead = Lead(
                company_name=raw_lead.company_name,
                website=raw_lead.website,
                country=raw_lead.country,
                industry=industry,
                product_interest=product_interest,
                source_url=raw_lead.source_url,
                contact_hint=raw_lead.contact_hint or raw_lead.contact_email or raw_lead.contact_phone,
                demand_summary=raw_lead.demand_summary or raw_lead.description,
                demand_posted_at=raw_lead.demand_posted_at,
                buyer_contact_name=raw_lead.buyer_contact_name,
                contact_email=raw_lead.contact_email,
                contact_phone=raw_lead.contact_phone,
                demand_type=raw_lead.demand_type,
                score=score.total,
                score_reason=f"{score.reason}; Role assessment: {role_reason}",
                status=status,
                discovered_at=as_of,
            )
            if lead.demand_posted_at and lead.demand_posted_at < freshness_cutoff:
                continue
            self.db.add(lead)
            self.db.flush()
            leads.append(lead)
            deduper.register_lead(lead)
            deduper.register_raw(raw_lead)
        self.db.commit()
        leads = sorted(
            leads,
            key=lambda lead: (self._status_priority(lead.status), lead.score),
            reverse=True,
        )
        self.last_run_stats = {
            "leads": len(leads),
            "duplicates_skipped": duplicates_skipped + self._fetch_duplicates_skipped,
        }
        self.last_archive_path = str(
            self.archive_writer.write(run_at=as_of, leads=leads, run_name=run_name)
        )
        return leads

    def _fetch_raw_leads(self, *, as_of: datetime):
        collected = []
        seen_urls: set[str] = set()
        raw_deduper = LeadDeduper([])
        for query in load_lead_queries()[: self.settings.lead_query_limit]:
            if len(collected) >= self.settings.lead_daily_min_records:
                break
            try:
                if query.provider == "duckduckgo-html":
                    results = self.search_connector.fetch(query)
                elif query.provider == "easytenders-search":
                    results = self.easytenders_search_connector.fetch(query)
                elif query.provider == "canadabuys-notice":
                    results = self.canadabuys_notice_connector.fetch(query)
                elif query.provider == "merx-notice":
                    results = self.merx_notice_connector.fetch(query)
                elif query.provider == "merx-search":
                    results = self.merx_search_connector.fetch(query)
                elif query.provider == "tenders-wa-listing":
                    results = self.tenders_wa_connector.fetch(query)
                elif query.provider == "tasmania-tenders-listing":
                    results = self.tasmania_tenders_connector.fetch(query)
                elif query.provider == "vendorpanel-rss":
                    results = self.vendorpanel_rss_connector.fetch(query)
                elif query.provider == "service-bund-search":
                    results = self.service_bund_connector.fetch(query)
                elif query.provider == "easytenders-notice":
                    results = self.easytenders_notice_connector.fetch(query)
                elif query.provider == "ungm-notice-search":
                    results = self.ungm_notice_connector.fetch(query)
                elif query.provider == "go4worldbusiness-buyer-listing":
                    results = self.go4worldbusiness_buyer_connector.fetch(
                        query,
                        max_results=self.settings.lead_search_max_results,
                        as_of=as_of,
                    )
                elif query.provider == "europages-listing":
                    results = self.europages_connector.fetch(
                        query,
                        max_results=self.settings.lead_search_max_results,
                    )
                elif query.provider == "environmental-expert-browser":
                    results = self.environmental_expert_connector.fetch(
                        query,
                        max_results=self.settings.lead_search_max_results,
                    )
                else:
                    continue
            except Exception:
                continue
            for result in results:
                if result.source_url in seen_urls:
                    self._fetch_duplicates_skipped += 1
                    continue
                if raw_deduper.is_duplicate_in_run(result):
                    self._fetch_duplicates_skipped += 1
                    continue
                seen_urls.add(result.source_url)
                raw_deduper.register_raw(result)
                collected.append(result)
        if collected:
            return collected
        return []

    def _refresh_existing_lead(self, lead: Lead, *, raw_lead, as_of: datetime) -> None:
        lead.website = raw_lead.website or lead.website
        lead.contact_hint = raw_lead.contact_hint or raw_lead.contact_email or raw_lead.contact_phone
        lead.demand_summary = raw_lead.demand_summary or lead.demand_summary
        lead.demand_posted_at = raw_lead.demand_posted_at or lead.demand_posted_at
        lead.buyer_contact_name = raw_lead.buyer_contact_name or lead.buyer_contact_name
        lead.contact_email = raw_lead.contact_email or lead.contact_email
        lead.contact_phone = raw_lead.contact_phone or lead.contact_phone
        lead.demand_type = raw_lead.demand_type or lead.demand_type
        lead.discovered_at = as_of
        if lead.status == "unknown" and raw_lead.demand_posted_at:
            lead.status = "buyer_review"
        self.db.add(lead)
        self.db.flush()

    @staticmethod
    def _resolve_status(*, raw_lead, role: str, reason: str) -> tuple[str, str]:
        status = role
        resolved_reason = reason
        if raw_lead.demand_posted_at and role == "unknown":
            status = "buyer_review"
            resolved_reason = f"{reason}; recent procurement date detected"
        if raw_lead.demand_posted_at and (raw_lead.contact_email or raw_lead.contact_phone) and role in {
            "unknown",
            "buyer_review",
        }:
            status = "buyer_candidate"
            resolved_reason = f"{resolved_reason}; recent procurement date and direct contact verified"
        return status, resolved_reason

    def _resolve_product_interest(self, description: str, product_hint: str | None) -> str:
        inferred = self.classifier.infer_product_interest(description)
        if inferred == "wire mesh" and product_hint:
            return product_hint
        return inferred

    @staticmethod
    def _status_priority(status: str) -> int:
        priorities = {
            "buyer_candidate": 4,
            "channel_candidate": 3,
            "buyer_review": 2,
            "unknown": 1,
            "supplier_noise": 0,
        }
        return priorities.get(status, 0)
