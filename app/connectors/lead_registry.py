import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class LeadQueryConfig:
    name: str
    provider: str
    query: str
    country: str
    product_interest: str | None = None
    allowed_domains: list[str] | None = None
    url: str | None = None
    enabled: bool = True


def _registry_path(filename: str) -> Path:
    return Path(__file__).resolve().parent.parent / "data" / filename


def load_lead_queries() -> list[LeadQueryConfig]:
    """加载并解析潜在客户查询配置
    
    从 lead_queries.json 文件中加载潜在客户查询配置，
    将其转换为 LeadQueryConfig 对象列表，并过滤出启用的配置。
    
    Returns:
        list[LeadQueryConfig]: 启用状态的潜在客户查询配置列表
    """
    # 构建 lead_queries.json 文件的路径
    path = _registry_path("lead_queries.json")
    
    # 如果文件不存在，返回空列表
    if not path.exists():
        return []

    # 读取并解析 JSON 文件
    payload = json.loads(path.read_text(encoding="utf-8"))
    
    # 存储解析后的配置对象
    queries: list[LeadQueryConfig] = []
    
    # 遍历每个配置项，创建 LeadQueryConfig 对象
    for item in payload:
        queries.append(
            LeadQueryConfig(
                name=item["name"],                # 配置名称
                provider=item["provider"],          # 数据提供方
                query=item["query"],                # 查询语句
                country=item["country"],            # 目标国家
                product_interest=item.get("product_interest"),  # 产品兴趣（可选）
                allowed_domains=item.get("allowed_domains"),    # 限定域名（可选）
                url=item.get("url"),                          # 直接来源 URL（可选）
                enabled=item.get("enabled", True),  # 启用状态（默认为 True）
            )
        )
    
    # 过滤出启用状态的配置并返回
    return [query for query in queries if query.enabled]
