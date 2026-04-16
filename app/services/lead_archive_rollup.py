from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.services.lead_deduper import LeadDeduper


@dataclass(slots=True)
class ArchivedLeadRow:
    archive_path: str
    run_name: str
    run_timestamp: datetime | None
    company_name: str
    status: str
    score: float | None
    country: str
    demand_type: str
    demand_posted_at: datetime | None
    industry: str
    product_interest: str
    demand_summary: str
    website: str
    source_url: str
    buyer_contact_name: str
    contact_email: str
    contact_phone: str
    contact_hint: str
    discovered_at: datetime | None
    score_reason: str

    @property
    def source_domain(self) -> str:
        match = re.match(r"https?://([^/]+)", self.source_url.strip())
        return match.group(1).lower() if match else ""

    @property
    def normalized_source_url(self) -> str:
        return LeadDeduper._normalize_url(self.source_url)

    @property
    def notice_fingerprint(self) -> str:
        company = LeadDeduper._normalize_text(self.company_name)
        summary = LeadDeduper._normalize_summary(self.demand_summary)
        date_key = LeadDeduper._normalize_date(self.demand_posted_at)
        return "|".join(part for part in [company, date_key, summary] if part)

    @property
    def contact_fingerprint(self) -> str:
        company = LeadDeduper._normalize_text(self.company_name)
        date_key = LeadDeduper._normalize_date(self.demand_posted_at)
        email = self.normalized_email
        phone = self.normalized_phone
        if not company or not date_key:
            return ""
        if not email and not phone:
            return ""
        return "|".join(part for part in [company, date_key, email, phone] if part)

    @property
    def normalized_email(self) -> str:
        if not self.contact_email or self.contact_email in {"N/A", "./."}:
            return ""
        return LeadDeduper._normalize_email(self.contact_email)

    @property
    def normalized_phone(self) -> str:
        if not self.contact_phone or self.contact_phone == "N/A":
            return ""
        return LeadDeduper._normalize_phone(self.contact_phone)


@dataclass(slots=True)
class UniqueArchivedLead:
    row: ArchivedLeadRow
    occurrences: int = 1
    archives: set[str] = field(default_factory=set)
    run_names: set[str] = field(default_factory=set)
    statuses: Counter[str] = field(default_factory=Counter)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

    def register(self, row: ArchivedLeadRow) -> None:
        self.occurrences += 1
        self.archives.add(row.archive_path)
        self.run_names.add(row.run_name)
        self.statuses[row.status] += 1
        self.first_seen_at = _min_dt(self.first_seen_at, row.discovered_at or row.run_timestamp)
        self.last_seen_at = _max_dt(self.last_seen_at, row.discovered_at or row.run_timestamp)
        if row.score is not None and (self.row.score is None or row.score > self.row.score):
            self.row = row


class LeadArchiveRollupWriter:
    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def write(self, *, generated_at: datetime | None = None) -> Path:
        run_at = generated_at or datetime.now()
        archive_files = sorted(self.root.glob("*/*.md"))
        rows = self._parse_archives(archive_files)
        unique_rows, duplicates = self._dedupe_rows(rows)

        output_dir = self.root / "_summary" / run_at.strftime("%Y%m%d_%H%M%S_%f")
        output_dir.mkdir(parents=True, exist_ok=True)

        rollup_md = output_dir / "lead_archive_rollup.md"
        all_csv = output_dir / "lead_archive_all_rows.csv"
        unique_csv = output_dir / "lead_archive_unique_rows.csv"
        duplicates_csv = output_dir / "lead_archive_duplicates.csv"

        rollup_md.write_text(
            "\n".join(
                self._build_markdown(
                    generated_at=run_at,
                    archive_files=archive_files,
                    rows=rows,
                    unique_rows=unique_rows,
                    duplicates=duplicates,
                )
            )
            + "\n",
            encoding="utf-8",
        )
        self._write_all_rows_csv(all_csv, rows)
        self._write_unique_rows_csv(unique_csv, unique_rows)
        self._write_duplicates_csv(duplicates_csv, duplicates)
        return output_dir.resolve()

    def _parse_archives(self, archive_files: list[Path]) -> list[ArchivedLeadRow]:
        rows: list[ArchivedLeadRow] = []
        for path in archive_files:
            rows.extend(self._parse_archive(path))
        return rows

    def _parse_archive(self, path: Path) -> list[ArchivedLeadRow]:
        lines = path.read_text(encoding="utf-8").splitlines()
        run_name = ""
        run_timestamp: datetime | None = None
        current_heading = ""
        current_fields: dict[str, str] = {}
        rows: list[ArchivedLeadRow] = []

        for line in lines:
            if line.startswith("- Run Name: "):
                run_name = line.removeprefix("- Run Name: ").strip()
                continue
            if line.startswith("- Timestamp: "):
                run_timestamp = _parse_datetime(line.removeprefix("- Timestamp: ").strip())
                continue
            if line.startswith("### "):
                if current_heading and current_fields:
                    rows.append(
                        self._row_from_fields(
                            archive_path=str(path.resolve()),
                            run_name=run_name,
                            run_timestamp=run_timestamp,
                            heading=current_heading,
                            fields=current_fields,
                        )
                    )
                current_heading = re.sub(r"^###\s+\d+\.\s+", "", line).strip()
                current_fields = {}
                continue
            if current_heading and line.startswith("- "):
                if ": " not in line:
                    continue
                key, value = line[2:].split(": ", 1)
                current_fields[key.strip()] = value.strip()

        if current_heading and current_fields:
            rows.append(
                self._row_from_fields(
                    archive_path=str(path.resolve()),
                    run_name=run_name,
                    run_timestamp=run_timestamp,
                    heading=current_heading,
                    fields=current_fields,
                )
            )
        return rows

    def _row_from_fields(
        self,
        *,
        archive_path: str,
        run_name: str,
        run_timestamp: datetime | None,
        heading: str,
        fields: dict[str, str],
    ) -> ArchivedLeadRow:
        return ArchivedLeadRow(
            archive_path=archive_path,
            run_name=run_name,
            run_timestamp=run_timestamp,
            company_name=heading,
            status=fields.get("Status", "unknown"),
            score=_parse_float(fields.get("Score")),
            country=fields.get("Country", ""),
            demand_type=fields.get("Demand Type", ""),
            demand_posted_at=_parse_datetime(fields.get("Demand Posted At", "")),
            industry=fields.get("Industry", ""),
            product_interest=fields.get("Product Interest", ""),
            demand_summary=fields.get("Demand Summary", ""),
            website=fields.get("Website", ""),
            source_url=fields.get("Source URL", ""),
            buyer_contact_name=fields.get("Buyer Contact", ""),
            contact_email=fields.get("Contact Email", ""),
            contact_phone=fields.get("Contact Phone", ""),
            contact_hint=fields.get("Contact Hint", ""),
            discovered_at=_parse_datetime(fields.get("Discovered At", "")),
            score_reason=fields.get("Score Reason", ""),
        )

    def _dedupe_rows(
        self,
        rows: list[ArchivedLeadRow],
    ) -> tuple[list[UniqueArchivedLead], list[tuple[str, ArchivedLeadRow, ArchivedLeadRow]]]:
        by_source_url: dict[str, UniqueArchivedLead] = {}
        by_contact_fingerprint: dict[str, UniqueArchivedLead] = {}
        by_notice_fingerprint: dict[str, UniqueArchivedLead] = {}
        unique_items: list[UniqueArchivedLead] = []
        duplicates: list[tuple[str, ArchivedLeadRow, ArchivedLeadRow]] = []

        for row in rows:
            existing, dedupe_key = self._find_existing_unique(
                row=row,
                by_source_url=by_source_url,
                by_contact_fingerprint=by_contact_fingerprint,
                by_notice_fingerprint=by_notice_fingerprint,
            )

            if not existing:
                unique = UniqueArchivedLead(
                    row=row,
                    occurrences=1,
                    archives={row.archive_path},
                    run_names={row.run_name},
                    statuses=Counter({row.status: 1}),
                    first_seen_at=row.discovered_at or row.run_timestamp,
                    last_seen_at=row.discovered_at or row.run_timestamp,
                )
                unique_items.append(unique)
                self._register_unique(
                    unique=unique,
                    row=row,
                    by_source_url=by_source_url,
                    by_contact_fingerprint=by_contact_fingerprint,
                    by_notice_fingerprint=by_notice_fingerprint,
                )
                continue

            duplicates.append((dedupe_key, row, existing.row))
            existing.register(row)
            self._register_unique(
                unique=existing,
                row=row,
                by_source_url=by_source_url,
                by_contact_fingerprint=by_contact_fingerprint,
                by_notice_fingerprint=by_notice_fingerprint,
            )

        unique_rows = sorted(
            unique_items,
            key=lambda item: (
                item.row.demand_posted_at or datetime.min,
                item.row.score or 0,
                item.row.company_name,
            ),
            reverse=True,
        )
        return unique_rows, duplicates

    @staticmethod
    def _find_existing_unique(
        *,
        row: ArchivedLeadRow,
        by_source_url: dict[str, UniqueArchivedLead],
        by_contact_fingerprint: dict[str, UniqueArchivedLead],
        by_notice_fingerprint: dict[str, UniqueArchivedLead],
    ) -> tuple[UniqueArchivedLead | None, str]:
        if row.normalized_source_url and row.normalized_source_url in by_source_url:
            return by_source_url[row.normalized_source_url], f"source:{row.normalized_source_url}"
        if row.contact_fingerprint and row.contact_fingerprint in by_contact_fingerprint:
            return by_contact_fingerprint[row.contact_fingerprint], f"contact:{row.contact_fingerprint}"
        if row.notice_fingerprint and row.notice_fingerprint in by_notice_fingerprint:
            return by_notice_fingerprint[row.notice_fingerprint], f"notice:{row.notice_fingerprint}"
        fallback = f"fallback:{LeadDeduper._normalize_text(row.company_name)}|{LeadDeduper._normalize_summary(row.demand_summary)}"
        return None, fallback

    @staticmethod
    def _register_unique(
        *,
        unique: UniqueArchivedLead,
        row: ArchivedLeadRow,
        by_source_url: dict[str, UniqueArchivedLead],
        by_contact_fingerprint: dict[str, UniqueArchivedLead],
        by_notice_fingerprint: dict[str, UniqueArchivedLead],
    ) -> None:
        if row.normalized_source_url:
            by_source_url[row.normalized_source_url] = unique
        if row.contact_fingerprint:
            by_contact_fingerprint[row.contact_fingerprint] = unique
        if row.notice_fingerprint:
            by_notice_fingerprint[row.notice_fingerprint] = unique

    def _build_markdown(
        self,
        *,
        generated_at: datetime,
        archive_files: list[Path],
        rows: list[ArchivedLeadRow],
        unique_rows: list[UniqueArchivedLead],
        duplicates: list[tuple[str, ArchivedLeadRow, ArchivedLeadRow]],
    ) -> list[str]:
        status_counts = Counter(row.status for row in rows)
        unique_status_counts = Counter(item.row.status for item in unique_rows)
        country_counts = Counter(item.row.country for item in unique_rows)
        domain_counts = Counter(item.row.source_domain for item in unique_rows if item.row.source_domain)

        lines = [
            "# Lead Archive Rollup",
            "",
            f"- Generated At: {generated_at.isoformat()}",
            f"- Archive Files Scanned: {len(archive_files)}",
            f"- Total Archived Lead Rows: {len(rows)}",
            f"- Unique Lead Rows: {len(unique_rows)}",
            f"- Duplicate Rows Removed: {len(duplicates)}",
            f"- Raw Status Counts: {self._counter_text(status_counts)}",
            f"- Unique Status Counts: {self._counter_text(unique_status_counts)}",
            f"- Unique Country Counts: {self._counter_text(country_counts)}",
            f"- Unique Source Domains: {self._counter_text(domain_counts)}",
            "",
            "## Unique Leads",
            "",
            "| Company | Country | Demand Posted At | Status | Occurrences | Contact Email | Contact Phone | Source URL |",
            "| --- | --- | --- | --- | ---: | --- | --- | --- |",
        ]

        for item in unique_rows:
            row = item.row
            lines.append(
                "| {company} | {country} | {posted_at} | {status} | {occurrences} | {email} | {phone} | {source_url} |".format(
                    company=_md_escape(row.company_name),
                    country=_md_escape(row.country),
                    posted_at=row.demand_posted_at.date().isoformat() if row.demand_posted_at else "N/A",
                    status=_md_escape(row.status),
                    occurrences=item.occurrences,
                    email=_md_escape(row.contact_email or "N/A"),
                    phone=_md_escape(row.contact_phone or "N/A"),
                    source_url=_md_escape(row.source_url),
                )
            )

        if duplicates:
            lines.extend(
                [
                    "",
                    "## Duplicate Examples",
                    "",
                    "| Dedupe Key | Duplicate Company | Canonical Company | Duplicate Archive |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for dedupe_key, duplicate_row, canonical_row in duplicates[:40]:
                lines.append(
                    "| {key} | {duplicate} | {canonical} | {archive} |".format(
                        key=_md_escape(dedupe_key),
                        duplicate=_md_escape(duplicate_row.company_name),
                        canonical=_md_escape(canonical_row.company_name),
                        archive=_md_escape(Path(duplicate_row.archive_path).name),
                    )
                )
        return lines

    @staticmethod
    def _write_all_rows_csv(path: Path, rows: list[ArchivedLeadRow]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "archive_path",
                    "run_name",
                    "run_timestamp",
                    "company_name",
                    "status",
                    "score",
                    "country",
                    "demand_type",
                    "demand_posted_at",
                    "industry",
                    "product_interest",
                    "demand_summary",
                    "website",
                    "source_url",
                    "buyer_contact_name",
                    "contact_email",
                    "contact_phone",
                    "contact_hint",
                    "discovered_at",
                    "score_reason",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row.archive_path,
                        row.run_name,
                        _dt_to_text(row.run_timestamp),
                        row.company_name,
                        row.status,
                        row.score if row.score is not None else "",
                        row.country,
                        row.demand_type,
                        _dt_to_text(row.demand_posted_at),
                        row.industry,
                        row.product_interest,
                        row.demand_summary,
                        row.website,
                        row.source_url,
                        row.buyer_contact_name,
                        row.contact_email,
                        row.contact_phone,
                        row.contact_hint,
                        _dt_to_text(row.discovered_at),
                        row.score_reason,
                    ]
                )

    @staticmethod
    def _write_unique_rows_csv(path: Path, unique_rows: list[UniqueArchivedLead]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "company_name",
                    "country",
                    "status",
                    "score",
                    "occurrences",
                    "first_seen_at",
                    "last_seen_at",
                    "demand_posted_at",
                    "demand_summary",
                    "contact_email",
                    "contact_phone",
                    "buyer_contact_name",
                    "source_url",
                    "source_domain",
                    "run_names",
                    "status_history",
                ]
            )
            for item in unique_rows:
                row = item.row
                writer.writerow(
                    [
                        row.company_name,
                        row.country,
                        row.status,
                        row.score if row.score is not None else "",
                        item.occurrences,
                        _dt_to_text(item.first_seen_at),
                        _dt_to_text(item.last_seen_at),
                        _dt_to_text(row.demand_posted_at),
                        row.demand_summary,
                        row.contact_email,
                        row.contact_phone,
                        row.buyer_contact_name,
                        row.source_url,
                        row.source_domain,
                        " | ".join(sorted(item.run_names)),
                        " | ".join(f"{status}:{count}" for status, count in sorted(item.statuses.items())),
                    ]
                )

    @staticmethod
    def _write_duplicates_csv(
        path: Path,
        duplicates: list[tuple[str, ArchivedLeadRow, ArchivedLeadRow]],
    ) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "dedupe_key",
                    "duplicate_company",
                    "duplicate_archive_path",
                    "duplicate_source_url",
                    "canonical_company",
                    "canonical_archive_path",
                    "canonical_source_url",
                ]
            )
            for dedupe_key, duplicate_row, canonical_row in duplicates:
                writer.writerow(
                    [
                        dedupe_key,
                        duplicate_row.company_name,
                        duplicate_row.archive_path,
                        duplicate_row.source_url,
                        canonical_row.company_name,
                        canonical_row.archive_path,
                        canonical_row.source_url,
                    ]
                )

    @staticmethod
    def _counter_text(counter: Counter[str]) -> str:
        if not counter:
            return "none"
        return ", ".join(f"{key}={count}" for key, count in sorted(counter.items()))


def _parse_datetime(value: str) -> datetime | None:
    cleaned = (value or "").strip()
    if not cleaned or cleaned in {"N/A", "./."}:
        return None
    cleaned = cleaned.replace("Z", "+00:00")
    for parser in (
        lambda raw: datetime.fromisoformat(raw),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d"),
    ):
        try:
            return parser(cleaned)
        except ValueError:
            continue
    return None


def _parse_float(value: str | None) -> float | None:
    cleaned = (value or "").strip()
    if not cleaned or cleaned == "N/A":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _dt_to_text(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _min_dt(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _max_dt(left: datetime | None, right: datetime | None) -> datetime | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def _md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
