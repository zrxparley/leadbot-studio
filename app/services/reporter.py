from collections.abc import Sequence
from datetime import datetime

from app.core.llm_client import LLMClient
from app.db.models import Lead, MaterialPrice, NewsItem


class ReportBuilder:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def build_daily_briefing(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
        news_items: Sequence[NewsItem],
        top_leads: Sequence[Lead],
        material_prices: Sequence[MaterialPrice],
    ) -> str:
        price_lines = [
            f"- {item.material_name} ({item.market}): {item.price} {item.currency}/{item.unit}"
            for item in material_prices
        ] or ["- No price updates collected"]
        news_lines = [
            f"- {item.title}: {item.summary}"
            for item in news_items[:5]
        ] or ["- No market news collected"]
        lead_lines = [
            (
                f"- {lead.company_name} | {lead.country} | {lead.status} | "
                f"score {lead.score:.0f} | {lead.product_interest} | "
                f"{self._format_demand_date(lead)} | "
                f"{lead.contact_email or 'no-email'} | {lead.contact_phone or 'no-phone'}"
            )
            for lead in top_leads[:5]
        ] or ["- No new high-priority leads"]

        prompt = "\n".join(
            [
                f"# 全球丝网市场动态日报",
                f"统计区间：{period_start:%Y-%m-%d %H:%M} 至 {period_end:%Y-%m-%d %H:%M}",
                "",
                "## 原材料动态",
                *price_lines,
                "",
                "## 政策与行业动态",
                *news_lines,
                "",
                "## 新发现重点客户",
                *lead_lines,
                "",
                "## 建议动作",
                "- 优先跟进评分最高且具备过滤/筛分需求的客户。",
                "- 对涉及不锈钢原料波动的报价保持日度复核。",
            ]
        )
        return self.llm.generate_report(prompt)

    def build_weekly_lead_summary(
        self, *, period_start: datetime, period_end: datetime, leads: Sequence[Lead]
    ) -> str:
        lead_lines = [
            (
                f"- {lead.company_name} | {lead.country} | {lead.status} | {lead.industry} | "
                f"{lead.product_interest} | {lead.demand_summary or 'N/A'} | "
                f"{self._format_demand_date(lead)} | "
                f"{lead.contact_email or 'no-email'} | {lead.contact_phone or 'no-phone'} | "
                f"score {lead.score:.0f}"
            )
            for lead in leads
            if lead.status != "supplier_noise"
        ][:20] or ["- No leads collected this week"]
        prompt = "\n".join(
            [
                "# 本周潜在线索汇总",
                f"统计区间：{period_start:%Y-%m-%d} 至 {period_end:%Y-%m-%d}",
                "",
                "## 高价值线索",
                *lead_lines,
                "",
                "## 建议动作",
                "- 按国家和产品需求拆分给对应销售。",
                "- 优先验证前 10 条线索的采购联系人与项目背景。",
            ]
        )
        return self.llm.generate_report(prompt)

    @staticmethod
    def _format_demand_date(lead: Lead) -> str:
        if not lead.demand_posted_at:
            return "no-date"
        return lead.demand_posted_at.strftime("%Y-%m-%d")
