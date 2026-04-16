from dataclasses import dataclass

from app.core.llm_client import LLMClient


class NewsClassifier:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def classify(self, title: str, body: str) -> list[str]:
        return self.llm.classify_news(f"{title}\n{body}")


@dataclass(slots=True)
class LeadRoleAssessment:
    role: str
    buyer_signal_count: int
    supplier_signal_count: int
    channel_signal_count: int
    reason: str


class LeadClassifier:
    buyer_signals = {
        "buyer",
        "buyer from",
        "buyer of",
        "procurement",
        "purchase",
        "purchasing",
        "quotations",
        "quotation",
        "quantity required",
        "looking for suppliers",
        "payment terms",
        "shipping terms",
        "destination",
        "wanted",
        "sourcing",
        "integrator",
        "contractor",
        "engineering",
        "epc",
        "oem",
        "importer",
        "process equipment",
        "water treatment",
        "chemical plant",
        "food processing",
        "pharmaceutical",
        "filtration system",
        "screening equipment",
        "replacement parts",
        "maintenance",
    }
    supplier_signals = {
        "manufacturer",
        "supplier",
        "exporter",
        "factory",
        "producer",
        "wholesaler",
        "mesh manufacturer",
        "wire mesh supplier",
        "our products",
        "product catalog",
        "stockist",
    }
    channel_signals = {
        "distributor",
        "dealer",
        "reseller",
        "trading company",
        "trading co",
        "stockholder",
    }

    def classify_industry(self, description: str) -> str:
        lowered = description.lower()
        if "filtration" in lowered or "filter" in lowered:
            return "industrial filtration"
        if "screen" in lowered or "mesh" in lowered:
            return "screening equipment"
        return "industrial manufacturing"

    def infer_product_interest(self, description: str) -> str:
        lowered = description.lower()
        if "316l" in lowered:
            return "316L stainless steel mesh"
        if "stainless" in lowered:
            return "stainless steel mesh"
        if "filtration" in lowered or "filter" in lowered:
            return "industrial filtration mesh"
        if "screening" in lowered:
            return "industrial screening media"
        return "wire mesh"

    def assess_company_role(
        self,
        *,
        company_name: str,
        description: str,
        source_url: str,
        search_query: str | None = None,
    ) -> LeadRoleAssessment:
        haystack = " ".join([company_name, description, source_url]).lower()
        buyer_count = sum(1 for signal in self.buyer_signals if signal in haystack)
        supplier_count = sum(1 for signal in self.supplier_signals if signal in haystack)
        channel_count = sum(1 for signal in self.channel_signals if signal in haystack)

        if buyer_count >= max(supplier_count + 1, 2):
            role = "buyer_candidate"
            reason = "Buyer-side signals outweigh supplier language"
        elif channel_count >= 1 and supplier_count <= buyer_count + 1:
            role = "channel_candidate"
            reason = "Distributor or trading language suggests a possible channel partner"
        elif supplier_count >= max(buyer_count + 1, 2) or (
            supplier_count >= 1 and buyer_count <= supplier_count and channel_count == 0
        ):
            role = "supplier_noise"
            reason = "Supplier-side wording dominates the page"
        elif buyer_count >= 1:
            role = "buyer_review"
            reason = "Some buyer-side signals found but intent is mixed"
        else:
            role = "unknown"
            reason = "Role signals are weak and need manual review"

        return LeadRoleAssessment(
            role=role,
            buyer_signal_count=buyer_count,
            supplier_signal_count=supplier_count,
            channel_signal_count=channel_count,
            reason=reason,
        )
