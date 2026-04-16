from datetime import datetime, timedelta

from app.connectors.base import RawLeadRecord, RawNewsRecord


class MockNewsConnector:
    name = "mock-industry-news"

    def fetch(self) -> list[RawNewsRecord]:
        now = datetime.now()
        return [
            RawNewsRecord(
                source_name=self.name,
                title="European filtration demand shows steady growth",
                url="https://example.com/news/eu-filtration-growth",
                body="Industrial filtration buyers in Germany are expanding stainless steel mesh demand.",
                published_at=now - timedelta(hours=6),
            ),
            RawNewsRecord(
                source_name=self.name,
                title="Nickel prices remain volatile in Asian trading",
                url="https://example.com/news/nickel-volatility",
                body="Nickel and stainless steel input costs stayed volatile, affecting export quotations.",
                published_at=now - timedelta(hours=4),
            ),
        ]


class MockLeadConnector:
    name = "mock-public-directory"

    def fetch(self) -> list[RawLeadRecord]:
        return [
            RawLeadRecord(
                source_name=self.name,
                company_name="Bavaria Process Filters GmbH",
                website="https://example.com/bavaria-process-filters",
                country="Germany",
                description="Supplier and integrator of industrial filtration systems for food and chemical plants.",
                source_url="https://example.com/directory/bavaria-process-filters",
                contact_hint="https://example.com/bavaria-process-filters/contact",
                product_hint="industrial filtration mesh",
                search_query="mock filtration integrator",
            ),
            RawLeadRecord(
                source_name=self.name,
                company_name="Saigon Industrial Screening Co.",
                website="https://example.com/saigon-industrial-screening",
                country="Vietnam",
                description="Engineering contractor with procurement needs for stainless wire mesh and screening media.",
                source_url="https://example.com/directory/saigon-industrial-screening",
                contact_hint="mailto:sales@example.com",
                product_hint="stainless steel mesh",
                search_query="mock screening contractor",
            ),
        ]
