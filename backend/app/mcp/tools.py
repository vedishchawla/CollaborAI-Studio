"""General-Purpose MCP Tool Implementations for CollaborAI.

Provides a set of domain-agnostic tools that any specialist agent can invoke
during their analysis phase. Tools are designed to be reusable across different
multi-agent systems — they are NOT tied to any specific business domain.

Users can register additional custom tools via the MCPToolRegistry API.
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import math
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from .protocol import MCPTool, MCPToolParameter, MCPToolRegistry

logger = logging.getLogger("collaborai.mcp.tools")


# ---------------------------------------------------------------------------
# Tool 1: Web Search  (general-purpose information retrieval)
# ---------------------------------------------------------------------------

async def web_search_handler(args: Dict[str, Any]) -> Any:
    """Simulate a web search returning relevant results for any query.

    In production this would call a real search API (Google, Bing, Tavily, etc.).
    The simulation uses deterministic seeding so results are reproducible.
    """
    query = args.get("query", "")
    max_results = min(int(args.get("max_results", 5)), 10)
    await asyncio.sleep(0.1)  # Simulate network latency

    seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    domains = [
        "reuters.com", "bloomberg.com", "nature.com", "arxiv.org",
        "who.int", "sec.gov", "ieee.org", "mckinsey.com",
        "gartner.com", "statista.com", "nih.gov", "europa.eu",
        "wikipedia.org", "scholar.google.com", "techcrunch.com",
    ]
    templates = [
        "Recent analysis indicates that {q} shows significant implications for stakeholders.",
        "A comprehensive 2024 study evaluates factors associated with {q}.",
        "Industry experts project substantial developments in {q} over the next 3-5 years.",
        "Technical feasibility assessment for {q} identifies key dependencies.",
        "Landscape analysis reveals emerging trends related to {q}.",
        "Policy and governance frameworks around {q} are evolving rapidly.",
        "Cost-benefit analysis suggests that {q} requires careful phased implementation.",
    ]

    results = []
    for i in range(min(max_results, len(templates))):
        results.append({
            "title": f"Analysis: {query[:60]} – Report {rng.randint(2023, 2025)}",
            "url": f"https://{rng.choice(domains)}/articles/{hashlib.md5((query + str(i)).encode()).hexdigest()[:10]}",
            "snippet": rng.choice(templates).format(q=query.lower()),
            "relevance_score": round(rng.uniform(0.7, 0.98), 2),
        })

    return {
        "query": query,
        "results_count": len(results),
        "results": results,
        "source": "MCP Web Search (simulated)",
    }


WEB_SEARCH_TOOL = MCPTool(
    name="web_search",
    description="Search the web for information on any topic. Returns ranked results with titles, URLs, and snippets. Useful for grounding claims in external evidence.",
    category="research",
    parameters=[
        MCPToolParameter(name="query", type="string", description="Search query string", required=True),
        MCPToolParameter(name="max_results", type="number", description="Maximum results to return (1-10)", default=5),
    ],
)


# ---------------------------------------------------------------------------
# Tool 2: Text Summarizer  (condense any long text)
# ---------------------------------------------------------------------------

async def text_summarizer_handler(args: Dict[str, Any]) -> Any:
    """Summarize a block of text into a shorter form.

    In production this would call an LLM summarization endpoint.
    The simulation extracts key sentences heuristically.
    """
    text = args.get("text", "")
    max_sentences = int(args.get("max_sentences", 3))
    style = args.get("style", "concise")  # concise | detailed | bullets
    await asyncio.sleep(0.08)

    # Simple extractive summarization simulation
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip() and len(s.strip()) > 15]
    if not sentences:
        return {"summary": text[:200], "style": style, "sentence_count": 0}

    # Score sentences by position and length (first and longer = more important)
    scored = []
    for i, s in enumerate(sentences):
        score = len(s.split()) * 0.3 + (len(sentences) - i) * 0.7
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)

    selected = [s for _, s in scored[:max_sentences]]

    if style == "bullets":
        summary = "\n".join(f"• {s}." for s in selected)
    else:
        summary = ". ".join(selected) + "."

    return {
        "summary": summary,
        "style": style,
        "original_length": len(text),
        "summary_length": len(summary),
        "compression_ratio": round(len(summary) / max(len(text), 1), 2),
        "sentences_extracted": len(selected),
    }


TEXT_SUMMARIZER_TOOL = MCPTool(
    name="text_summarizer",
    description="Summarize any block of text into a shorter form. Supports concise, detailed, or bullet-point styles. Useful for condensing findings, reports, or research passages.",
    category="analysis",
    parameters=[
        MCPToolParameter(name="text", type="string", description="Text content to summarize", required=True),
        MCPToolParameter(name="max_sentences", type="number", description="Maximum sentences in summary", default=3),
        MCPToolParameter(name="style", type="string", description="Summary style: concise, detailed, or bullets", default="concise"),
    ],
)


# ---------------------------------------------------------------------------
# Tool 3: Calculator  (general-purpose numeric computation)
# ---------------------------------------------------------------------------

async def calculator_handler(args: Dict[str, Any]) -> Any:
    """Perform general numeric calculations.

    Supports basic arithmetic, percentage, ratio, and common financial
    formulas (ROI, NPV, breakeven). The expression is evaluated safely.
    """
    operation = args.get("operation", "evaluate")
    params = args.get("parameters", {})
    await asyncio.sleep(0.05)

    if operation == "evaluate":
        # Safe arithmetic expression evaluation
        expression = str(params.get("expression", "0"))
        # Allow only digits, operators, parens, dots, spaces
        sanitized = re.sub(r'[^0-9+\-*/().%^ ]', '', expression)
        try:
            result_val = eval(sanitized, {"__builtins__": {}}, {"math": math})  # noqa: S307
            return {"operation": "evaluate", "expression": expression, "result": result_val}
        except Exception as e:
            return {"operation": "evaluate", "expression": expression, "error": str(e)}

    elif operation == "percentage":
        value = float(params.get("value", 0))
        total = float(params.get("total", 100))
        pct = (value / total) * 100 if total != 0 else 0
        return {"operation": "percentage", "value": value, "total": total, "percentage": round(pct, 2)}

    elif operation == "ratio":
        a = float(params.get("a", 0))
        b = float(params.get("b", 1))
        return {"operation": "ratio", "a": a, "b": b, "ratio": round(a / b, 4) if b != 0 else "infinity"}

    elif operation == "roi":
        investment = float(params.get("investment", 100000))
        revenue = float(params.get("projected_revenue", 150000))
        roi = ((revenue - investment) / investment) * 100
        return {
            "operation": "ROI",
            "investment": investment,
            "projected_revenue": revenue,
            "roi_percent": round(roi, 2),
            "verdict": "Positive" if roi > 0 else "Negative",
        }

    elif operation == "npv":
        cash_flows = params.get("cash_flows", [-100000, 30000, 40000, 50000, 60000])
        discount_rate = float(params.get("discount_rate", 0.1))
        npv = sum(cf / (1 + discount_rate) ** i for i, cf in enumerate(cash_flows))
        return {
            "operation": "NPV",
            "cash_flows": cash_flows,
            "discount_rate": discount_rate,
            "npv": round(npv, 2),
            "verdict": "Viable" if npv > 0 else "Not viable",
        }

    elif operation == "breakeven":
        fixed_costs = float(params.get("fixed_costs", 50000))
        unit_price = float(params.get("unit_price", 100))
        variable_cost = float(params.get("variable_cost_per_unit", 40))
        if unit_price <= variable_cost:
            return {"operation": "breakeven", "error": "Unit price must exceed variable cost"}
        breakeven_units = fixed_costs / (unit_price - variable_cost)
        return {
            "operation": "breakeven",
            "fixed_costs": fixed_costs,
            "breakeven_units": round(breakeven_units),
            "breakeven_revenue": round(breakeven_units * unit_price, 2),
        }

    elif operation == "statistics":
        values = params.get("values", [])
        if not values:
            return {"operation": "statistics", "error": "No values provided"}
        n = len(values)
        mean = sum(values) / n
        sorted_v = sorted(values)
        median = sorted_v[n // 2] if n % 2 else (sorted_v[n // 2 - 1] + sorted_v[n // 2]) / 2
        variance = sum((x - mean) ** 2 for x in values) / n
        return {
            "operation": "statistics",
            "count": n,
            "mean": round(mean, 4),
            "median": round(median, 4),
            "min": min(values),
            "max": max(values),
            "std_dev": round(math.sqrt(variance), 4),
        }

    else:
        return {"error": f"Unknown operation: {operation}. Supported: evaluate, percentage, ratio, roi, npv, breakeven, statistics"}


CALCULATOR_TOOL = MCPTool(
    name="calculator",
    description="Perform general numeric calculations including arithmetic expressions, percentages, ratios, ROI, NPV, breakeven analysis, and basic statistics. A universal computation tool for any agent domain.",
    category="calculation",
    parameters=[
        MCPToolParameter(name="operation", type="string", description="Operation type: evaluate, percentage, ratio, roi, npv, breakeven, statistics", required=True),
        MCPToolParameter(name="parameters", type="object", description="Operation-specific parameters (e.g. {expression}, {value, total}, {investment, projected_revenue}, {cash_flows, discount_rate}, {values})", required=True),
    ],
)


# ---------------------------------------------------------------------------
# Tool 4: Data Analyzer  (extract insights from structured data)
# ---------------------------------------------------------------------------

async def data_analyzer_handler(args: Dict[str, Any]) -> Any:
    """Analyze structured data and return insights.

    Accepts a list of records (dicts) and performs aggregation, comparison,
    or trend analysis. In production, this could connect to a real analytics service.
    """
    data = args.get("data", [])
    analysis_type = args.get("analysis_type", "summary")
    group_by = args.get("group_by", None)
    metric = args.get("metric", None)
    await asyncio.sleep(0.08)

    if not data:
        return {"analysis_type": analysis_type, "error": "No data provided", "record_count": 0}

    record_count = len(data)
    fields = list(data[0].keys()) if isinstance(data[0], dict) else []

    if analysis_type == "summary":
        # Provide field-level summary
        field_summaries = {}
        for field in fields:
            values = [r.get(field) for r in data if r.get(field) is not None]
            numeric = [v for v in values if isinstance(v, (int, float))]
            if numeric:
                field_summaries[field] = {
                    "type": "numeric",
                    "count": len(numeric),
                    "min": min(numeric),
                    "max": max(numeric),
                    "mean": round(sum(numeric) / len(numeric), 2),
                }
            else:
                unique = list(set(str(v) for v in values))
                field_summaries[field] = {
                    "type": "categorical",
                    "count": len(values),
                    "unique_values": len(unique),
                    "sample": unique[:5],
                }
        return {
            "analysis_type": "summary",
            "record_count": record_count,
            "fields": fields,
            "field_summaries": field_summaries,
        }

    elif analysis_type == "group" and group_by:
        groups: Dict[str, list] = {}
        for r in data:
            key = str(r.get(group_by, "unknown"))
            groups.setdefault(key, []).append(r)
        group_summary = {}
        for key, records in groups.items():
            group_summary[key] = {"count": len(records)}
            if metric:
                vals = [r.get(metric) for r in records if isinstance(r.get(metric), (int, float))]
                if vals:
                    group_summary[key]["metric_mean"] = round(sum(vals) / len(vals), 2)
                    group_summary[key]["metric_sum"] = round(sum(vals), 2)
        return {
            "analysis_type": "group",
            "group_by": group_by,
            "metric": metric,
            "group_count": len(groups),
            "groups": group_summary,
        }

    elif analysis_type == "compare":
        # Compare first and last records
        first, last = data[0], data[-1]
        diffs = {}
        for field in fields:
            v1, v2 = first.get(field), last.get(field)
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                diffs[field] = {"first": v1, "last": v2, "change": round(v2 - v1, 2), "change_pct": round(((v2 - v1) / v1) * 100, 2) if v1 != 0 else None}
        return {
            "analysis_type": "compare",
            "record_count": record_count,
            "comparisons": diffs,
        }

    else:
        return {"error": f"Unknown analysis_type: {analysis_type}. Supported: summary, group, compare"}


DATA_ANALYZER_TOOL = MCPTool(
    name="data_analyzer",
    description="Analyze structured data (list of records). Supports summary statistics, group-by aggregation, and first-vs-last comparison. Any agent can use this to extract insights from tabular data.",
    category="analysis",
    parameters=[
        MCPToolParameter(name="data", type="array", description="List of data records (objects/dicts) to analyze", required=True),
        MCPToolParameter(name="analysis_type", type="string", description="Type of analysis: summary, group, compare", default="summary"),
        MCPToolParameter(name="group_by", type="string", description="Field name to group by (for 'group' analysis)", default=None),
        MCPToolParameter(name="metric", type="string", description="Numeric field to aggregate within groups", default=None),
    ],
)


# ---------------------------------------------------------------------------
# Tool 5: Document Retriever  (simulate document/knowledge-base lookup)
# ---------------------------------------------------------------------------

async def document_retriever_handler(args: Dict[str, Any]) -> Any:
    """Retrieve relevant documents or knowledge-base entries for a query.

    In production this would connect to a vector store, RAG pipeline, or
    document database. The simulation returns plausible structured results.
    """
    query = args.get("query", "")
    source = args.get("source", "knowledge_base")
    max_docs = min(int(args.get("max_docs", 3)), 10)
    await asyncio.sleep(0.1)

    seed = int(hashlib.md5(f"{query}{source}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    doc_types = ["policy_document", "technical_spec", "research_paper", "report", "guideline", "standard", "white_paper"]
    topics = query.lower().split()[:3]
    topic_str = " ".join(topics) if topics else "general"

    documents = []
    for i in range(max_docs):
        doc_id = hashlib.md5(f"{query}{i}".encode()).hexdigest()[:8]
        documents.append({
            "doc_id": f"DOC-{doc_id}",
            "title": f"{rng.choice(doc_types).replace('_', ' ').title()}: {topic_str.title()} – {rng.choice(['Analysis', 'Framework', 'Assessment', 'Overview', 'Guidelines'])} {rng.randint(2022, 2025)}",
            "source": source,
            "relevance_score": round(rng.uniform(0.65, 0.96), 2),
            "excerpt": f"This document addresses key aspects of {topic_str}, covering implications, requirements, and recommendations for stakeholders. Section {rng.randint(1, 8)}.{rng.randint(1, 5)} details the core framework.",
            "metadata": {
                "pages": rng.randint(5, 120),
                "last_updated": f"2024-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
                "classification": rng.choice(["public", "internal", "confidential"]),
            },
        })

    return {
        "query": query,
        "source": source,
        "documents_found": len(documents),
        "documents": documents,
    }


DOCUMENT_RETRIEVER_TOOL = MCPTool(
    name="document_retriever",
    description="Retrieve relevant documents from a knowledge base, document store, or policy repository. Useful for grounding analysis in organizational documents, standards, or prior research.",
    category="research",
    parameters=[
        MCPToolParameter(name="query", type="string", description="Search query for document retrieval", required=True),
        MCPToolParameter(name="source", type="string", description="Document source: knowledge_base, policy_store, research_db, standards", default="knowledge_base"),
        MCPToolParameter(name="max_docs", type="number", description="Maximum documents to retrieve (1-10)", default=3),
    ],
)


# ---------------------------------------------------------------------------
# Global Registry Setup
# ---------------------------------------------------------------------------

def create_default_registry() -> MCPToolRegistry:
    """Create and populate the default MCP tool registry with general-purpose tools.

    These tools are domain-agnostic and can be used by any specialist agent.
    Additional domain-specific tools can be registered at runtime via
    ``registry.register(tool, handler)``.
    """
    registry = MCPToolRegistry()
    registry.register(WEB_SEARCH_TOOL, web_search_handler)
    registry.register(TEXT_SUMMARIZER_TOOL, text_summarizer_handler)
    registry.register(CALCULATOR_TOOL, calculator_handler)
    registry.register(DATA_ANALYZER_TOOL, data_analyzer_handler)
    registry.register(DOCUMENT_RETRIEVER_TOOL, document_retriever_handler)
    return registry


# Module-level list for imports
BUILTIN_TOOLS = [
    WEB_SEARCH_TOOL,
    TEXT_SUMMARIZER_TOOL,
    CALCULATOR_TOOL,
    DATA_ANALYZER_TOOL,
    DOCUMENT_RETRIEVER_TOOL,
]
