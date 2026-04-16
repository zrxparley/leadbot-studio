from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class RawNewsRecord:
    source_name: str
    title: str
    url: str
    body: str
    published_at: datetime
    country: str | None = None
    language: str = "en"


@dataclass(slots=True)
class RawLeadRecord:
    source_name: str
    company_name: str
    website: str
    country: str
    description: str
    source_url: str
    contact_hint: str | None = None
    product_hint: str | None = None
    search_query: str | None = None
    demand_summary: str | None = None
    demand_posted_at: datetime | None = None
    buyer_contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    demand_type: str | None = None


class BaseConnector:
    name: str
