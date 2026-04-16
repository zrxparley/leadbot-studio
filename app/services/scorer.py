from dataclasses import dataclass


@dataclass(slots=True)
class LeadScore:
    total: float
    reason: str


class LeadScorer:
    def score(
        self,
        *,
        country_match: bool,
        keyword_match_count: int,
        industry_match: bool,
        has_contact_hint: bool,
        has_direct_contact: bool,
        website_depth: bool,
        role: str,
        buyer_signal_count: int,
        supplier_signal_count: int,
        channel_signal_count: int,
    ) -> LeadScore:
        total = 0.0
        reasons: list[str] = []
        if country_match:
            total += 15
            reasons.append("Target country matched")
        if keyword_match_count:
            keyword_points = min(keyword_match_count * 10, 30)
            total += keyword_points
            reasons.append(f"{keyword_match_count} product keywords matched")
        if industry_match:
            total += 30
            reasons.append("Industry profile fits industrial filtration/screening")
        if has_contact_hint:
            total += 15
            reasons.append("Website or contact entry available")
        if has_direct_contact:
            total += 20
            reasons.append("Direct buyer email or phone found")
        if website_depth:
            total += 10
            reasons.append("Specific company page discovered via public web search")
        if role == "buyer_candidate":
            total += 25
            reasons.append(f"Buyer fit is strong ({buyer_signal_count} buyer-side signals)")
        elif role == "channel_candidate":
            total += 12
            reasons.append(
                f"Possible distributor or channel partner ({channel_signal_count} channel signals)"
            )
        elif role == "buyer_review":
            total += 8
            reasons.append("Mixed wording but still shows buyer-side intent")
        elif role == "supplier_noise":
            total -= 20
            reasons.append(f"Supplier noise detected ({supplier_signal_count} supplier-side signals)")
        total = max(0.0, min(total, 100.0))
        if total < 50:
            reasons.append("Needs manual review before outreach")
        return LeadScore(total=total, reason="; ".join(reasons))
