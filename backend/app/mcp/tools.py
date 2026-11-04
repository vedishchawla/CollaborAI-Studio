"""Built-in MCP Tool Implementations for CollaborAI.

Provides a set of domain-relevant tools that specialist agents can invoke
during their analysis phase to augment their reasoning with external data.
"""

from __future__ import annotations
import asyncio
import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List

from .protocol import MCPTool, MCPToolParameter, MCPToolRegistry

logger = logging.getLogger("collaborai.mcp.tools")


# ---------------------------------------------------------------------------
# Tool 1: Web Search (Simulated)
# ---------------------------------------------------------------------------

async def web_search_handler(args: Dict[str, Any]) -> Any:
    """Simulate a web search returning relevant domain results."""
    query = args.get("query", "")
    max_results = args.get("max_results", 5)
    await asyncio.sleep(0.1)  # Simulate network latency

    # Generate deterministic but realistic-looking search results
    seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    domains = [
        "reuters.com", "bloomberg.com", "nature.com", "arxiv.org",
        "who.int", "sec.gov", "ieee.org", "mckinsey.com",
        "gartner.com", "statista.com", "nih.gov", "europa.eu"
    ]
    snippets = [
        f"Recent analysis indicates that {query.lower()} shows significant implications for market dynamics.",
        f"Regulatory frameworks around {query.lower()} are evolving rapidly across major jurisdictions.",
        f"Industry experts project substantial growth in areas related to {query.lower()} over the next 3-5 years.",
        f"A comprehensive study published in 2024 evaluates the risk factors associated with {query.lower()}.",
        f"Cost-benefit analysis suggests that {query.lower()} requires careful phased implementation.",
        f"Technical feasibility assessment for {query.lower()} identifies key infrastructure dependencies.",
        f"Competitive landscape analysis reveals emerging trends in {query.lower()}.",
    ]

    results = []
    for i in range(min(max_results, len(snippets))):
        results.append({
            "title": f"Analysis: {query[:60]} – Insight Report {rng.randint(2023, 2025)}",
            "url": f"https://{rng.choice(domains)}/reports/{hashlib.md5((query + str(i)).encode()).hexdigest()[:10]}",
            "snippet": rng.choice(snippets),
            "relevance_score": round(rng.uniform(0.7, 0.98), 2)
        })

    return {
        "query": query,
        "results_count": len(results),
        "results": results,
        "search_engine": "CollaborAI Research Engine",
    }


WEB_SEARCH_TOOL = MCPTool(
    name="web_search",
    description="Search the web for recent research, regulatory filings, market data, and domain-specific information to augment specialist analysis.",
    category="research",
    parameters=[
        MCPToolParameter(name="query", type="string", description="Search query", required=True),
        MCPToolParameter(name="max_results", type="number", description="Maximum results to return (1-10)", default=5),
    ]
)


# ---------------------------------------------------------------------------
# Tool 2: Regulatory Database Lookup
# ---------------------------------------------------------------------------

async def regulatory_lookup_handler(args: Dict[str, Any]) -> Any:
    """Simulate regulatory database queries."""
    jurisdiction = args.get("jurisdiction", "US")
    domain = args.get("domain", "general")
    query = args.get("query", "")
    await asyncio.sleep(0.1)

    seed = int(hashlib.md5(f"{jurisdiction}{domain}{query}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    statutes = {
        "US": ["21 CFR Part 820", "FAA Part 107", "OSHA 29 CFR 1910", "FTC Act Section 5"],
        "EU": ["EU AI Act (Regulation 2024/1689)", "GDPR Article 22", "MDR 2017/745", "EU Machinery Regulation 2023/1230"],
        "BR": ["ANATEL Resolution 715", "ANVISA RDC 185", "Lei Geral de Proteção de Dados (LGPD)"],
        "GLOBAL": ["ISO 27001:2022", "ISO 13485:2016", "IEC 62304", "ISO 14971:2019"],
    }

    applicable = statutes.get(jurisdiction.upper(), statutes["GLOBAL"])
    compliance_timeline_weeks = rng.randint(4, 24)

    return {
        "jurisdiction": jurisdiction,
        "domain": domain,
        "applicable_regulations": applicable[:3],
        "compliance_timeline_weeks": compliance_timeline_weeks,
        "key_requirements": [
            f"Mandatory certification period: {compliance_timeline_weeks} weeks",
            f"Required documentation: Technical file, risk assessment, clinical evaluation",
            f"Penalty for non-compliance: Fines up to {rng.choice(['€20M', '$500K', 'R$50M'])} or market withdrawal",
        ],
        "last_updated": "2024-11-01",
        "confidence": round(rng.uniform(0.8, 0.95), 2),
    }


REGULATORY_LOOKUP_TOOL = MCPTool(
    name="regulatory_lookup",
    description="Query regulatory databases for applicable statutes, compliance timelines, and certification requirements across jurisdictions (US, EU, BR, GLOBAL).",
    category="domain_lookup",
    parameters=[
        MCPToolParameter(name="jurisdiction", type="string", description="Jurisdiction code (US, EU, BR, GLOBAL)", required=True),
        MCPToolParameter(name="domain", type="string", description="Regulatory domain (medical, aviation, fintech, robotics, general)", required=True),
        MCPToolParameter(name="query", type="string", description="Specific regulatory query", default=""),
    ]
)


# ---------------------------------------------------------------------------
# Tool 3: Financial Calculator
# ---------------------------------------------------------------------------

async def financial_calculator_handler(args: Dict[str, Any]) -> Any:
    """Perform financial calculations (ROI, NPV, breakeven, margin analysis)."""
    calculation_type = args.get("calculation_type", "roi")
    params = args.get("parameters", {})
    await asyncio.sleep(0.05)

    if calculation_type == "roi":
        investment = float(params.get("investment", 100000))
        revenue = float(params.get("projected_revenue", 150000))
        roi = ((revenue - investment) / investment) * 100
        return {
            "calculation": "ROI",
            "investment": investment,
            "projected_revenue": revenue,
            "roi_percent": round(roi, 2),
            "verdict": "Positive" if roi > 0 else "Negative",
        }
    elif calculation_type == "breakeven":
        fixed_costs = float(params.get("fixed_costs", 50000))
        unit_price = float(params.get("unit_price", 100))
        variable_cost = float(params.get("variable_cost_per_unit", 40))
        if unit_price <= variable_cost:
            return {"calculation": "Breakeven", "error": "Unit price must exceed variable cost"}
        breakeven_units = fixed_costs / (unit_price - variable_cost)
        return {
            "calculation": "Breakeven",
            "fixed_costs": fixed_costs,
            "breakeven_units": round(breakeven_units),
            "breakeven_revenue": round(breakeven_units * unit_price, 2),
        }
    elif calculation_type == "npv":
        cash_flows = params.get("cash_flows", [-100000, 30000, 40000, 50000, 60000])
        discount_rate = float(params.get("discount_rate", 0.1))
        npv = sum(cf / (1 + discount_rate) ** i for i, cf in enumerate(cash_flows))
        return {
            "calculation": "NPV",
            "cash_flows": cash_flows,
            "discount_rate": discount_rate,
            "npv": round(npv, 2),
            "verdict": "Viable" if npv > 0 else "Not viable",
        }
    else:
        return {"error": f"Unknown calculation type: {calculation_type}"}


FINANCIAL_CALCULATOR_TOOL = MCPTool(
    name="financial_calculator",
    description="Perform financial calculations including ROI analysis, breakeven computation, and NPV (Net Present Value) projections.",
    category="calculation",
    parameters=[
        MCPToolParameter(name="calculation_type", type="string", description="Type: roi, breakeven, npv", required=True),
        MCPToolParameter(name="parameters", type="object", description="Calculation-specific parameters (investment, revenue, costs, cash_flows, discount_rate)", required=True),
    ]
)


# ---------------------------------------------------------------------------
# Tool 4: Risk Assessment Matrix
# ---------------------------------------------------------------------------

async def risk_assessment_handler(args: Dict[str, Any]) -> Any:
    """Generate structured risk assessment for a given scenario."""
    scenario = args.get("scenario", "")
    risk_category = args.get("category", "operational")
    await asyncio.sleep(0.08)

    seed = int(hashlib.md5(f"{scenario}{risk_category}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    risk_factors = [
        {"factor": "Implementation delay", "likelihood": rng.choice(["Low", "Medium", "High"]),
         "impact": rng.choice(["Medium", "High", "Critical"]), "mitigation": "Phased rollout with contingency buffers"},
        {"factor": "Regulatory non-compliance", "likelihood": rng.choice(["Low", "Medium"]),
         "impact": "Critical", "mitigation": "Pre-submission regulatory engagement and parallel certification tracks"},
        {"factor": "Budget overrun", "likelihood": rng.choice(["Medium", "High"]),
         "impact": rng.choice(["Medium", "High"]), "mitigation": "Fixed-price contracts with 15% contingency reserve"},
        {"factor": "Technology integration failure", "likelihood": rng.choice(["Low", "Medium"]),
         "impact": rng.choice(["High", "Critical"]), "mitigation": "Proof-of-concept validation before full deployment"},
    ]

    overall_score = round(rng.uniform(3.5, 8.5), 1)
    return {
        "scenario": scenario,
        "category": risk_category,
        "overall_risk_score": overall_score,
        "risk_level": "High" if overall_score > 7 else "Medium" if overall_score > 4 else "Low",
        "risk_factors": risk_factors[:3],
        "recommendation": "Proceed with enhanced monitoring" if overall_score < 6 else "Requires executive risk acceptance",
    }


RISK_ASSESSMENT_TOOL = MCPTool(
    name="risk_assessment",
    description="Generate a structured risk assessment matrix with likelihood, impact, and mitigation strategies for a given scenario.",
    category="domain_lookup",
    parameters=[
        MCPToolParameter(name="scenario", type="string", description="Risk scenario to assess", required=True),
        MCPToolParameter(name="category", type="string", description="Risk category (operational, financial, regulatory, technical)", default="operational"),
    ]
)


# ---------------------------------------------------------------------------
# Tool 5: Market Data Lookup
# ---------------------------------------------------------------------------

async def market_data_handler(args: Dict[str, Any]) -> Any:
    """Retrieve simulated market intelligence data."""
    market = args.get("market", "")
    metric = args.get("metric", "market_size")
    await asyncio.sleep(0.08)

    seed = int(hashlib.md5(f"{market}{metric}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    return {
        "market": market,
        "metric": metric,
        "data": {
            "current_value": f"${rng.randint(1, 500)}B",
            "growth_rate_cagr": f"{rng.uniform(3, 25):.1f}%",
            "forecast_2028": f"${rng.randint(5, 800)}B",
            "top_players": [f"Company {chr(65 + i)}" for i in range(rng.randint(3, 5))],
            "adoption_rate": f"{rng.uniform(10, 75):.0f}%",
        },
        "source": "CollaborAI Market Intelligence Engine",
        "last_updated": "2024-Q3",
    }


MARKET_DATA_TOOL = MCPTool(
    name="market_data",
    description="Retrieve market size, growth forecasts, competitive landscape, and adoption rates for specific market segments.",
    category="data_retrieval",
    parameters=[
        MCPToolParameter(name="market", type="string", description="Market segment to query", required=True),
        MCPToolParameter(name="metric", type="string", description="Metric type: market_size, growth, competition, adoption", default="market_size"),
    ]
)


# ---------------------------------------------------------------------------
# Global Registry Setup
# ---------------------------------------------------------------------------

def create_default_registry() -> MCPToolRegistry:
    """Create and populate the default MCP tool registry."""
    registry = MCPToolRegistry()
    registry.register(WEB_SEARCH_TOOL, web_search_handler)
    registry.register(REGULATORY_LOOKUP_TOOL, regulatory_lookup_handler)
    registry.register(FINANCIAL_CALCULATOR_TOOL, financial_calculator_handler)
    registry.register(RISK_ASSESSMENT_TOOL, risk_assessment_handler)
    registry.register(MARKET_DATA_TOOL, market_data_handler)
    return registry


# Module-level list for imports
BUILTIN_TOOLS = [
    WEB_SEARCH_TOOL,
    REGULATORY_LOOKUP_TOOL,
    FINANCIAL_CALCULATOR_TOOL,
    RISK_ASSESSMENT_TOOL,
    MARKET_DATA_TOOL,
]
