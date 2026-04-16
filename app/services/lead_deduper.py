import re
import unicodedata
from datetime import datetime

from app.connectors.base import RawLeadRecord
from app.db.models import Lead


class LeadDeduper:
    def __init__(self, existing_leads: list[Lead]) -> None:
        self._by_source_url: dict[str, Lead] = {}
        self._by_notice_fingerprint: dict[str, Lead] = {}
        self._by_contact_fingerprint: dict[str, Lead] = {}
        self._runtime_raw_keys: set[str] = set()
        for lead in existing_leads:
            self.register_lead(lead)

    def find_existing(self, raw_lead: RawLeadRecord) -> Lead | None:
        source_url = self._normalize_url(raw_lead.source_url)
        if source_url and source_url in self._by_source_url:
            return self._by_source_url[source_url]

        notice_fingerprint = self._notice_fingerprint_from_raw(raw_lead)
        if notice_fingerprint and notice_fingerprint in self._by_notice_fingerprint:
            return self._by_notice_fingerprint[notice_fingerprint]

        contact_fingerprint = self._contact_fingerprint_from_raw(raw_lead)
        if contact_fingerprint and contact_fingerprint in self._by_contact_fingerprint:
            return self._by_contact_fingerprint[contact_fingerprint]
        return None

    def is_duplicate_in_run(self, raw_lead: RawLeadRecord) -> bool:
        return any(key in self._runtime_raw_keys for key in self._raw_keys(raw_lead))

    def register_raw(self, raw_lead: RawLeadRecord) -> None:
        self._runtime_raw_keys.update(self._raw_keys(raw_lead))

    def register_lead(self, lead: Lead) -> None:
        source_url = self._normalize_url(lead.source_url)
        if source_url:
            self._by_source_url[source_url] = lead

        notice_fingerprint = self._notice_fingerprint_from_lead(lead)
        if notice_fingerprint:
            self._by_notice_fingerprint[notice_fingerprint] = lead

        contact_fingerprint = self._contact_fingerprint_from_lead(lead)
        if contact_fingerprint:
            self._by_contact_fingerprint[contact_fingerprint] = lead

    def _raw_keys(self, raw_lead: RawLeadRecord) -> set[str]:
        keys = set()
        source_url = self._normalize_url(raw_lead.source_url)
        if source_url:
            keys.add(f"source:{source_url}")

        notice_fingerprint = self._notice_fingerprint_from_raw(raw_lead)
        if notice_fingerprint:
            keys.add(f"notice:{notice_fingerprint}")

        contact_fingerprint = self._contact_fingerprint_from_raw(raw_lead)
        if contact_fingerprint:
            keys.add(f"contact:{contact_fingerprint}")
        return keys

    def _notice_fingerprint_from_raw(self, raw_lead: RawLeadRecord) -> str | None:
        company = self._normalize_text(raw_lead.company_name)
        summary = self._normalize_summary(raw_lead.demand_summary or raw_lead.description)
        date_key = self._normalize_date(raw_lead.demand_posted_at)
        if not company or not summary:
            return None
        return "|".join(part for part in [company, date_key, summary] if part)

    def _notice_fingerprint_from_lead(self, lead: Lead) -> str | None:
        company = self._normalize_text(lead.company_name)
        summary = self._normalize_summary(lead.demand_summary or "")
        date_key = self._normalize_date(lead.demand_posted_at)
        if not company or not summary:
            return None
        return "|".join(part for part in [company, date_key, summary] if part)

    def _contact_fingerprint_from_raw(self, raw_lead: RawLeadRecord) -> str | None:
        company = self._normalize_text(raw_lead.company_name)
        date_key = self._normalize_date(raw_lead.demand_posted_at)
        email = self._normalize_email(raw_lead.contact_email)
        phone = self._normalize_phone(raw_lead.contact_phone)
        if not company or not date_key:
            return None
        if not email and not phone:
            return None
        return "|".join(part for part in [company, date_key, email, phone] if part)

    def _contact_fingerprint_from_lead(self, lead: Lead) -> str | None:
        company = self._normalize_text(lead.company_name)
        date_key = self._normalize_date(lead.demand_posted_at)
        email = self._normalize_email(lead.contact_email)
        phone = self._normalize_phone(lead.contact_phone)
        if not company or not date_key:
            return None
        if not email and not phone:
            return None
        return "|".join(part for part in [company, date_key, email, phone] if part)

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        if not value:
            return ""
        normalized = unicodedata.normalize("NFKC", value).lower()
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _normalize_summary(value: str | None) -> str:
        cleaned = LeadDeduper._normalize_text(value)
        if not cleaned:
            return ""
        words = cleaned.split()
        return " ".join(words[:18])

    @staticmethod
    def _normalize_email(value: str | None) -> str:
        return value.strip().lower() if value else ""

    @staticmethod
    def _normalize_phone(value: str | None) -> str:
        return re.sub(r"\D", "", value or "")

    @staticmethod
    def _normalize_url(value: str | None) -> str:
        return value.strip().lower() if value else ""

    @staticmethod
    def _normalize_date(value: datetime | None) -> str:
        return value.strftime("%Y-%m-%d") if value else ""
