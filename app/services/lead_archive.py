from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from app.db.models import Lead


class LeadArchiveWriter:
    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def write(
        self,
        *,
        run_at: datetime,
        leads: Sequence[Lead],
        run_name: str,
    ) -> Path:
        timestamp = run_at.strftime("%Y%m%d_%H%M%S_%f")
        run_dir = self.root / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)
        archive_path = run_dir / f"{timestamp}.md"

        lines = self._build_markdown(
            run_at=run_at,
            leads=leads,
            run_name=run_name,
        )
        archive_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return archive_path.resolve()

    def _build_markdown(
        self,
        *,
        run_at: datetime,
        leads: Sequence[Lead],
        run_name: str,
    ) -> list[str]:
        status_counts = Counter(lead.status for lead in leads)
        lines = [
            "# Buyer Demand Run Archive",
            "",
            f"- Run Name: {run_name}",
            f"- Timestamp: {run_at.isoformat()}",
            f"- Total Leads: {len(leads)}",
            f"- Status Counts: {self._format_status_counts(status_counts)}",
            "",
            "## Leads",
        ]

        if not leads:
            lines.extend(["", "No leads generated in this run."])
            return lines

        for index, lead in enumerate(leads, start=1):
            lines.extend(
                [
                    "",
                    f"### {index}. {lead.company_name}",
                    f"- Status: {lead.status}",
                    f"- Score: {lead.score:.1f}",
                    f"- Country: {lead.country}",
                    f"- Demand Type: {lead.demand_type or 'N/A'}",
                    f"- Demand Posted At: {lead.demand_posted_at.isoformat() if lead.demand_posted_at else 'N/A'}",
                    f"- Industry: {lead.industry}",
                    f"- Product Interest: {lead.product_interest}",
                    f"- Demand Summary: {lead.demand_summary or 'N/A'}",
                    f"- Website: {lead.website}",
                    f"- Source URL: {lead.source_url}",
                    f"- Buyer Contact: {lead.buyer_contact_name or 'N/A'}",
                    f"- Contact Email: {lead.contact_email or 'N/A'}",
                    f"- Contact Phone: {lead.contact_phone or 'N/A'}",
                    f"- Contact Hint: {lead.contact_hint or 'N/A'}",
                    f"- Discovered At: {lead.discovered_at.isoformat()}",
                    f"- Score Reason: {lead.score_reason}",
                ]
            )

        return lines

    @staticmethod
    def _format_status_counts(status_counts: Counter[str]) -> str:
        if not status_counts:
            return "none"
        return ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
