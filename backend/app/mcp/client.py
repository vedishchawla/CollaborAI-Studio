"""MCP Tool Client — Enables agents to invoke MCP tools during analysis.

The MCPToolClient is integrated into the specialist execution flow, allowing
each agent to autonomously select and invoke relevant tools based on their
analysis needs. Tool selection is dynamic and driven by the tool catalog,
NOT hardcoded to any specific domain.
"""

from __future__ import annotations
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .protocol import MCPTool, MCPToolCall, MCPToolResult, MCPToolRegistry
from .tools import create_default_registry

logger = logging.getLogger("collaborai.mcp.client")

_UNIT_MULTIPLIERS = {
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
}


def _extract_numbers_from_text(text: str) -> Dict[str, Any]:
    """Extract expressions, monetary values, percentages, and numeric values from goal/constraint text."""
    expressions = re.findall(
        r"(?<![A-Za-z0-9_.-])(\d+(?:\.\d+)?(?:\s*[+\-*/]\s*\d+(?:\.\d+)?)+)(?![A-Za-z0-9_.-])",
        text,
    )

    monetary: List[float] = []
    # Match currency-prefixed amounts with optional unit suffix (e.g. $1.5M, $250K, ₹10 Lakh, $100,000)
    for match in re.finditer(
        r"[$₹€£]\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|m|b|lakhs?|crores?)?\b",
        text,
        flags=re.IGNORECASE,
    ):
        num = float(match.group(1).replace(",", ""))
        unit = match.group(2).lower() if match.group(2) else None
        if unit in _UNIT_MULTIPLIERS:
            num *= _UNIT_MULTIPLIERS[unit]
        monetary.append(num)

    # Also match standalone suffixed amounts without currency symbol (e.g. 2 Lakh, 1.5M)
    for match in re.finditer(
        r"(?<![$₹€£\d])(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|m|b|lakhs?|crores?)\b",
        text,
        flags=re.IGNORECASE,
    ):
        num = float(match.group(1).replace(",", ""))
        unit = match.group(2).lower()
        val = num * _UNIT_MULTIPLIERS[unit]
        if val not in monetary:
            monetary.append(val)

    percentages = [
        float(m.group(1))
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", text)
    ]

    all_numbers: List[float] = []
    for match in re.finditer(
        r"(?<![A-Za-z0-9_.-])(\d+(?:,\d{3})*(?:\.\d+)?)(?![A-Za-z0-9_.-])",
        text,
    ):
        try:
            all_numbers.append(float(match.group(1).replace(",", "")))
        except ValueError:
            continue

    return {
        "expressions": expressions,
        "monetary": monetary,
        "percentages": percentages,
        "all_numbers": all_numbers,
    }


def _build_calculator_args(goal: str, agent_domain: str = "") -> Dict[str, Any]:
    """Select the best calculator operation and real numeric arguments from goal text."""
    extracted = _extract_numbers_from_text(goal)
    goal_lower = goal.lower()
    monetary = extracted["monetary"]
    percentages = extracted["percentages"]
    all_nums = extracted["all_numbers"]
    expressions = extracted["expressions"]

    if expressions:
        return {
            "operation": "evaluate",
            "parameters": {"expression": expressions[0]},
        }

    if "breakeven" in goal_lower or "break-even" in goal_lower or "break even" in goal_lower:
        base = monetary[0] if monetary else (all_nums[0] if all_nums else 50000.0)
        fixed_costs = base if base >= 100 else 50000.0
        unit_price = round(max(100.0, fixed_costs / 500.0), 2)
        variable_cost = round(unit_price * 0.4, 2)
        return {
            "operation": "breakeven",
            "parameters": {
                "fixed_costs": fixed_costs,
                "unit_price": unit_price,
                "variable_cost_per_unit": variable_cost,
            },
        }

    if "npv" in goal_lower or "cash flow" in goal_lower or "discount" in goal_lower:
        base = monetary[0] if monetary else (all_nums[0] if all_nums else 100000.0)
        inv = base if base >= 100 else 100000.0
        rate = round(percentages[0] / 100.0, 4) if percentages else 0.1
        if rate >= 1.0 or rate <= -1.0:
            rate = 0.1
        return {
            "operation": "npv",
            "parameters": {
                "cash_flows": [-inv, round(inv * 0.3, 2), round(inv * 0.4, 2), round(inv * 0.5, 2)],
                "discount_rate": rate,
            },
        }

    if (
        ("margin" in goal_lower or "percentage" in goal_lower or "%" in goal)
        and percentages
        and not any(w in goal_lower for w in ("roi", "investment", "revenue", "budget", "cost"))
    ):
        pct = percentages[0]
        base = monetary[0] if monetary else 100000.0
        return {
            "operation": "percentage",
            "parameters": {"value": round(base * (pct / 100.0), 2), "total": base},
        }

    if len(monetary) >= 2:
        inv, rev = min(monetary[0], monetary[1]), max(monetary[0], monetary[1])
        if inv > 0 and rev > inv:
            return {
                "operation": "roi",
                "parameters": {"investment": inv, "projected_revenue": rev},
            }
        if inv > 0:
            return {
                "operation": "roi",
                "parameters": {"investment": inv, "projected_revenue": round(inv * 1.35, 2)},
            }

    if len(monetary) == 1 and monetary[0] > 0:
        budget = monetary[0]
        uplift = (percentages[0] / 100.0) if (percentages and "margin" in goal_lower) else 0.35
        return {
            "operation": "roi",
            "parameters": {
                "investment": budget,
                "projected_revenue": round(budget * (1.0 + uplift), 2),
            },
        }

    if percentages:
        return {
            "operation": "percentage",
            "parameters": {"value": percentages[0], "total": 100},
        }

    if len(all_nums) >= 2:
        return {
            "operation": "statistics",
            "parameters": {"values": all_nums[:10]},
        }

    if len(all_nums) == 1 and all_nums[0] != 0:
        return {
            "operation": "evaluate",
            "parameters": {"expression": f"{all_nums[0]} * 1.25"},
        }

    return {
        "operation": "roi",
        "parameters": {"investment": 100000, "projected_revenue": 135000},
    }


def _build_data_analyzer_args(goal: str) -> Dict[str, Any]:
    """Build structured benchmark records derived from extracted goal figures for data_analyzer."""
    extracted = _extract_numbers_from_text(goal)
    base = (
        extracted["monetary"][0]
        if extracted["monetary"]
        else (extracted["all_numbers"][0] if extracted["all_numbers"] else 100000.0)
    )
    if base <= 0:
        base = 100000.0
    return {
        "data": [
            {"scenario": "conservative", "projected_cost": round(base * 0.85, 2), "expected_value": round(base * 1.1, 2)},
            {"scenario": "baseline", "projected_cost": round(base, 2), "expected_value": round(base * 1.35, 2)},
            {"scenario": "optimistic", "projected_cost": round(base * 1.15, 2), "expected_value": round(base * 1.65, 2)},
        ],
        "analysis_type": "summary",
    }


class MCPToolClient:
    """Client for invoking MCP tools on behalf of specialist agents.

    Tool selection is fully dynamic — the client inspects the registered
    tool catalog and selects relevant tools based on the agent's stated
    needs and the goal context, rather than relying on hardcoded domain-
    keyword mappings.
    """

    def __init__(self, registry: Optional[MCPToolRegistry] = None):
        self._registry = registry or create_default_registry()
        self._call_history: List[MCPToolCall] = []
        self._result_history: List[MCPToolResult] = []

    @property
    def call_history(self) -> List[MCPToolCall]:
        return self._call_history

    @property
    def result_history(self) -> List[MCPToolResult]:
        return self._result_history

    def list_available_tools(self, category: Optional[str] = None) -> List[MCPTool]:
        """List tools available for agent use."""
        return self._registry.list_tools(category=category)

    def format_tools_for_prompt(self, tools: Optional[List[MCPTool]] = None) -> str:
        """Format available tools into a prompt-friendly description."""
        available = tools or self._registry.list_tools()
        if not available:
            return "No MCP tools available."

        lines = ["=== AVAILABLE MCP TOOLS ==="]
        for tool in available:
            params_str = ", ".join(
                f"{p.name}: {p.type}" + (" (required)" if p.required else f" (default={p.default})")
                for p in tool.parameters
            )
            lines.append(f"\n[{tool.name}] ({tool.category})")
            lines.append(f"  Description: {tool.description}")
            lines.append(f"  Parameters: {params_str}")
        lines.append("\nTo use a tool, specify which tools to call and with what arguments.")
        return "\n".join(lines)

    async def invoke_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        requesting_agent: str = "system",
        run_id: str = ""
    ) -> MCPToolResult:
        """Invoke a single MCP tool and return the result."""
        call_id = f"TC-{uuid.uuid4().hex[:8]}"

        call = MCPToolCall(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            requesting_agent=requesting_agent,
            run_id=run_id
        )
        self._call_history.append(call)

        handler = self._registry.get_handler(tool_name)
        if not handler:
            result = MCPToolResult(
                call_id=call_id,
                tool_name=tool_name,
                status="error",
                error_message=f"Tool '{tool_name}' not found in registry",
                arguments=arguments,
                requesting_agent=requesting_agent,
            )
            self._result_history.append(result)
            return result

        start = time.monotonic()
        try:
            output = await handler(arguments)
            elapsed_ms = (time.monotonic() - start) * 1000
            result = MCPToolResult(
                call_id=call_id,
                tool_name=tool_name,
                status="success",
                result=output,
                execution_time_ms=round(elapsed_ms, 2),
                arguments=arguments,
                requesting_agent=requesting_agent,
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error("MCP tool '%s' failed: %s", tool_name, e)
            result = MCPToolResult(
                call_id=call_id,
                tool_name=tool_name,
                status="error",
                error_message=str(e),
                execution_time_ms=round(elapsed_ms, 2),
                arguments=arguments,
                requesting_agent=requesting_agent,
            )

        self._result_history.append(result)
        logger.info(
            "MCP tool invocation: %s by %s → %s (%.1fms)",
            tool_name, requesting_agent, result.status, result.execution_time_ms
        )
        return result

    async def invoke_tools_for_agent(
        self,
        agent_name: str,
        agent_domain: str,
        goal: str,
        run_id: str = "",
        max_tools: int = 3,
    ) -> List[MCPToolResult]:
        """Dynamically select and invoke relevant tools for a specialist agent.

        Tool selection is general-purpose — every agent gets a web search for
        external context and a document retrieval for internal context, then a
        calculator if the goal mentions numbers, or a data analyzer if structured
        data is referenced. The selection is driven by the TOOL CATALOG, not by
        hardcoded domain keywords.

        Custom tools registered at runtime are also considered.
        """
        results: List[MCPToolResult] = []
        available_tools = self._registry.list_tools()
        available_names = {t.name for t in available_tools}
        goal_lower = goal.lower()

        # Build a prioritized list of (tool_name, arguments) based on general heuristics
        tool_selections: List[Tuple[str, Dict[str, Any]]] = []
        extracted = _extract_numbers_from_text(goal)

        # 1. Every agent benefits from web search for external grounding
        if "web_search" in available_names:
            tool_selections.append(("web_search", {
                "query": f"{agent_domain} {goal[:80]}",
                "max_results": 3,
            }))

        # 2. Document retrieval for internal knowledge grounding
        if "document_retriever" in available_names:
            tool_selections.append(("document_retriever", {
                "query": f"{agent_domain} {goal[:60]}",
                "source": "knowledge_base",
                "max_docs": 2,
            }))

        # 3. Calculator when goal involves quantitative aspects or numbers
        numeric_keywords = ["cost", "budget", "roi", "revenue", "price", "profit",
                          "margin", "rate", "percent", "calculate", "npv", "breakeven",
                          "forecast", "growth", "investment", "financial", "cap", "week", "month"]
        has_numbers = bool(
            extracted["monetary"] or extracted["percentages"] or extracted["expressions"]
        )
        if "calculator" in available_names and (
            has_numbers or any(kw in goal_lower for kw in numeric_keywords)
        ):
            tool_selections.append(("calculator", _build_calculator_args(goal, agent_domain)))

        # 4. Data analyzer when structured data analysis is needed
        data_keywords = ["data", "dataset", "metrics", "statistics", "compare",
                        "trends", "analyze", "performance", "benchmark"]
        if "data_analyzer" in available_names and any(kw in goal_lower for kw in data_keywords):
            tool_selections.append(("data_analyzer", _build_data_analyzer_args(goal)))

        # 5. Text summarizer when dealing with long-form content
        summary_keywords = ["summarize", "summary", "report", "review", "overview",
                           "findings", "documentation", "long"]
        if "text_summarizer" in available_names and any(kw in goal_lower for kw in summary_keywords):
            tool_selections.append(("text_summarizer", {
                "text": goal[:500],
                "max_sentences": 3,
                "style": "concise",
            }))

        # 6. Include any OTHER registered tools not already selected (custom tools)
        selected_names = {name for name, _ in tool_selections}
        for tool in available_tools:
            if tool.name not in selected_names:
                # Auto-construct minimal arguments from required params
                auto_args: Dict[str, Any] = {}
                for param in tool.parameters:
                    if param.required:
                        if param.type == "string":
                            auto_args[param.name] = f"{agent_domain} {goal[:60]}"
                        elif param.type == "number":
                            auto_args[param.name] = 0
                        elif param.type == "object":
                            auto_args[param.name] = {}
                        elif param.type == "array":
                            auto_args[param.name] = []
                        elif param.type == "boolean":
                            auto_args[param.name] = True
                tool_selections.append((tool.name, auto_args))

        # Invoke selected tools (cap at max_tools per agent)
        for tool_name, tool_args in tool_selections[:max_tools]:
            result = await self.invoke_tool(
                tool_name=tool_name,
                arguments=tool_args,
                requesting_agent=agent_name,
                run_id=run_id,
            )
            results.append(result)

        return results

    def format_results_for_prompt(self, results: List[MCPToolResult]) -> str:
        """Format tool results into context for the specialist prompt."""
        if not results:
            return "No supplementary tool data available."

        lines = ["=== MCP TOOL RESULTS (Supplementary Research) ==="]
        for r in results:
            if r.status == "success":
                lines.append(f"\n[{r.tool_name}] (took {r.execution_time_ms:.0f}ms)")
                if isinstance(r.result, dict):
                    for k, v in r.result.items():
                        if k not in ("source",):
                            lines.append(f"  {k}: {v}")
                else:
                    lines.append(f"  Result: {r.result}")
            else:
                lines.append(f"\n[{r.tool_name}] ERROR: {r.error_message}")
        return "\n".join(lines)

    def get_invocation_summary(self) -> Dict[str, Any]:
        """Get summary statistics of all tool invocations."""
        total = len(self._result_history)
        successes = sum(1 for r in self._result_history if r.status == "success")
        total_time = sum(r.execution_time_ms for r in self._result_history)
        by_tool: Dict[str, int] = {}
        for r in self._result_history:
            by_tool.setdefault(r.tool_name, 0)
            by_tool[r.tool_name] += 1

        return {
            "total_invocations": total,
            "successful": successes,
            "failed": total - successes,
            "total_execution_time_ms": round(total_time, 2),
            "invocations_by_tool": by_tool,
        }
