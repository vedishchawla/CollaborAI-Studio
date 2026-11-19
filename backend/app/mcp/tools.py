"""General-Purpose MCP Tool Implementations for CollaborAI.

Provides a set of domain-agnostic tools that any specialist agent can invoke
during their analysis phase. Tools are designed to be reusable across different
multi-agent systems — they are NOT tied to any specific business domain.

Users can register additional custom tools via the MCPToolRegistry API.
"""

from __future__ import annotations
import ast
import asyncio
import hashlib
import json
import logging
import math
import operator
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Union

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

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_MATH_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
    "log": math.log,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
}

_MATH_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}

_SUFFIX_MULTIPLIERS = {
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
}


def _normalize_math_expression(expression: str) -> str:
    """Normalize human-friendly math/financial strings for AST parsing."""
    expr = expression.strip()
    if not expr:
        return "0"
    # Replace caret exponentiation with Python power operator
    expr = expr.replace("^", "**")
    # Strip common currency symbols
    expr = re.sub(r"[$₹€£]", "", expr)
    # Remove thousands-separator commas (e.g. 100,000 -> 100000) without touching function arg commas
    expr = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", expr)

    # Expand shorthand suffixes (e.g. 1.5M -> 1500000, 50k -> 50000)
    def _expand_suffix(match: re.Match[str]) -> str:
        num = float(match.group(1))
        mult = _SUFFIX_MULTIPLIERS[match.group(2).lower()]
        val = num * mult
        return str(int(val)) if val.is_integer() else str(val)

    expr = re.sub(r"(?<![a-zA-Z_.])(\d+(?:\.\d+)?)\s*([kKmMbB])\b", _expand_suffix, expr)
    return expr


def _eval_ast_node(node: ast.AST) -> Union[int, float]:
    """Safely evaluate a whitelisted AST node representing a math expression."""
    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError(f"Unsupported constant value: {node.value!r}")
    if isinstance(node, ast.Name):
        key = node.id.lower()
        if key in _MATH_CONSTANTS:
            return _MATH_CONSTANTS[key]
        raise ValueError(f"Unknown identifier in expression: {node.id}")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        operand = _eval_ast_node(node.operand)
        return _UNARY_OPS[type(node.op)](operand)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left = _eval_ast_node(node.left)
        right = _eval_ast_node(node.right)
        # Guard against huge exponents causing hangs/memory errors
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("Exponent magnitude exceeds safe limit (1000)")
        return _BINARY_OPS[type(node.op)](left, right)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Unsupported function call syntax")
        func_name = node.func.id.lower()
        if func_name not in _MATH_FUNCTIONS:
            raise ValueError(f"Unsupported math function: {node.func.id}")
        if node.keywords:
            raise ValueError("Keyword arguments are not supported in math functions")
        call_args = [_eval_ast_node(arg) for arg in node.args]
        return _MATH_FUNCTIONS[func_name](*call_args)
    raise ValueError(f"Unsupported expression construct: {type(node).__name__}")


def _safe_eval_math(expression: str) -> Union[int, float]:
    """Parse and safely evaluate a mathematical expression using Python's AST."""
    normalized = _normalize_math_expression(expression)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid mathematical expression '{expression}': {exc.msg}") from exc
    result = _eval_ast_node(tree)
    if isinstance(result, float):
        # Clean floating point representation while preserving precision
        rounded = round(result, 8)
        if rounded.is_integer() and abs(rounded) < 1e15:
            return int(rounded)
        return rounded
    return result


def _to_float(val: Any, default: float = 0.0) -> float:
    """Coerce numbers or formatted numeric strings ($1.5M, 20%, 100,000) into float."""
    if val is None or isinstance(val, bool):
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.strip().rstrip("%")
        if not cleaned:
            return default
        normalized = _normalize_math_expression(cleaned)
        return float(normalized)
    raise ValueError(f"Cannot convert value {val!r} to number")


async def calculator_handler(args: Dict[str, Any]) -> Any:
    """Perform general numeric calculations.

    Supports AST-safe arithmetic expressions (with math functions and ^ exponents),
    percentage, ratio, ROI, NPV, breakeven, statistics, compound_growth, and margin.
    Accepts arguments nested under ``parameters`` or passed at top-level ``args``.
    """
    operation = str(args.get("operation", "evaluate")).strip().lower()
    raw_params = args.get("parameters")
    params: Dict[str, Any] = {k: v for k, v in args.items() if k not in ("operation", "parameters")}
    if isinstance(raw_params, dict):
        params.update(raw_params)

    await asyncio.sleep(0.05)

    try:
        if operation == "evaluate":
            expression = str(params.get("expression", "0"))
            try:
                result_val = _safe_eval_math(expression)
                return {"operation": "evaluate", "expression": expression, "result": result_val}
            except ZeroDivisionError:
                return {"operation": "evaluate", "expression": expression, "error": "Division by zero"}
            except Exception as e:
                return {"operation": "evaluate", "expression": expression, "error": str(e)}

        elif operation == "percentage":
            value = _to_float(params.get("value", 0))
            total = _to_float(params.get("total", 100))
            if total == 0:
                return {"operation": "percentage", "value": value, "total": total, "percentage": 0.0}
            pct = (value / total) * 100
            return {"operation": "percentage", "value": value, "total": total, "percentage": round(pct, 2)}

        elif operation == "ratio":
            a = _to_float(params.get("a", 0))
            b = _to_float(params.get("b", 1))
            return {"operation": "ratio", "a": a, "b": b, "ratio": round(a / b, 4) if b != 0 else "infinity"}

        elif operation == "roi":
            investment = _to_float(params.get("investment", 100000))
            revenue = _to_float(params.get("projected_revenue", 150000))
            if investment == 0:
                return {
                    "operation": "ROI",
                    "investment": investment,
                    "projected_revenue": revenue,
                    "error": "Investment cannot be zero for ROI calculation",
                }
            net_profit = revenue - investment
            roi = (net_profit / investment) * 100
            payback_multiple = revenue / investment
            return {
                "operation": "ROI",
                "investment": investment,
                "projected_revenue": revenue,
                "net_profit": round(net_profit, 2),
                "roi_percent": round(roi, 2),
                "payback_multiple": round(payback_multiple, 2),
                "verdict": "Positive" if roi > 0 else "Negative",
            }

        elif operation == "npv":
            raw_flows = params.get("cash_flows", [-100000, 30000, 40000, 50000, 60000])
            cash_flows = [_to_float(cf) for cf in raw_flows] if isinstance(raw_flows, list) else []
            if not cash_flows:
                return {"operation": "NPV", "error": "cash_flows must be a non-empty list of numbers"}
            discount_rate = _to_float(params.get("discount_rate", 0.1))
            if discount_rate <= -1:
                return {"operation": "NPV", "error": "discount_rate must be greater than -1"}
            npv = sum(cf / ((1 + discount_rate) ** i) for i, cf in enumerate(cash_flows))
            return {
                "operation": "NPV",
                "cash_flows": cash_flows,
                "discount_rate": discount_rate,
                "npv": round(npv, 2),
                "verdict": "Viable" if npv > 0 else "Not viable",
            }

        elif operation == "breakeven":
            fixed_costs = _to_float(params.get("fixed_costs", 50000))
            unit_price = _to_float(params.get("unit_price", 100))
            variable_cost = _to_float(params.get("variable_cost_per_unit", 40))
            if unit_price <= variable_cost:
                return {"operation": "breakeven", "error": "Unit price must exceed variable cost"}
            contribution_margin = unit_price - variable_cost
            breakeven_units = fixed_costs / contribution_margin
            return {
                "operation": "breakeven",
                "fixed_costs": fixed_costs,
                "unit_price": unit_price,
                "variable_cost_per_unit": variable_cost,
                "contribution_margin": round(contribution_margin, 2),
                "breakeven_units": round(breakeven_units),
                "breakeven_revenue": round(breakeven_units * unit_price, 2),
            }

        elif operation == "statistics":
            raw_values = params.get("values", [])
            if not raw_values or not isinstance(raw_values, list):
                return {"operation": "statistics", "error": "No values provided"}
            values = [v if isinstance(v, (int, float)) and not isinstance(v, bool) else _to_float(v) for v in raw_values]
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

        elif operation == "compound_growth":
            principal = _to_float(params.get("principal", params.get("initial_value", 100000)))
            rate_percent = _to_float(params.get("rate_percent", params.get("annual_rate", 10)))
            periods = int(_to_float(params.get("periods", 3)))
            if periods < 0:
                return {"operation": "compound_growth", "error": "periods must be non-negative"}
            final_value = principal * ((1 + rate_percent / 100) ** periods)
            total_growth = final_value - principal
            return {
                "operation": "compound_growth",
                "principal": principal,
                "rate_percent": rate_percent,
                "periods": periods,
                "final_value": round(final_value, 2),
                "total_growth": round(total_growth, 2),
                "growth_percent": round(((final_value - principal) / principal) * 100, 2) if principal != 0 else 0.0,
            }

        elif operation == "margin":
            revenue = _to_float(params.get("revenue", 100000))
            cost = _to_float(params.get("cost", 75000))
            if revenue == 0:
                return {"operation": "margin", "error": "Revenue cannot be zero for margin calculation"}
            gross_profit = revenue - cost
            gross_margin_pct = (gross_profit / revenue) * 100
            markup_pct = (gross_profit / cost) * 100 if cost != 0 else None
            return {
                "operation": "margin",
                "revenue": revenue,
                "cost": cost,
                "gross_profit": round(gross_profit, 2),
                "gross_margin_percent": round(gross_margin_pct, 2),
                "markup_percent": round(markup_pct, 2) if markup_pct is not None else None,
            }

        else:
            return {
                "error": (
                    f"Unknown operation: {operation}. Supported: evaluate, percentage, ratio, "
                    "roi, npv, breakeven, statistics, compound_growth, margin"
                )
            }
    except Exception as e:
        return {"operation": operation, "error": str(e)}


CALCULATOR_TOOL = MCPTool(
    name="calculator",
    description=(
        "Perform general numeric calculations including AST-safe arithmetic expressions "
        "(with sqrt, round, min, max, pow, log, ^), percentages, ratios, ROI, NPV, "
        "breakeven analysis, statistics, compound growth, and margin analysis."
    ),
    category="calculation",
    parameters=[
        MCPToolParameter(
            name="operation",
            type="string",
            description="Operation type: evaluate, percentage, ratio, roi, npv, breakeven, statistics, compound_growth, margin",
            required=True,
            default="evaluate",
        ),
        MCPToolParameter(
            name="parameters",
            type="object",
            description="Operation-specific parameters (e.g. {expression}, {value, total}, {investment, projected_revenue}, {cash_flows, discount_rate}, {values})",
            required=True,
            default={"expression": "(150000 - 100000) / 100000 * 100"},
        ),
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
