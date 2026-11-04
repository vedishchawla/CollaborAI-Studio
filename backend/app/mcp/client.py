"""MCP Tool Client — Enables agents to invoke MCP tools during analysis.

The MCPToolClient is integrated into the specialist execution flow, allowing
each agent to autonomously select and invoke relevant tools based on their
domain mandate before producing findings.
"""

from __future__ import annotations
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from .protocol import MCPTool, MCPToolCall, MCPToolResult, MCPToolRegistry
from .tools import create_default_registry

logger = logging.getLogger("collaborai.mcp.client")


class MCPToolClient:
    """Client for invoking MCP tools on behalf of specialist agents."""

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
        run_id: str = ""
    ) -> List[MCPToolResult]:
        """Automatically select and invoke relevant tools for a specialist agent.
        
        Uses domain heuristics to pick the most relevant 2-3 tools for each
        specialist, then invokes them to gather supplementary data.
        """
        results: List[MCPToolResult] = []
        domain_lower = agent_domain.lower()

        # Heuristic tool selection based on domain keywords
        tool_selections: List[tuple[str, Dict[str, Any]]] = []

        # Every agent gets a web search
        tool_selections.append(("web_search", {"query": f"{agent_domain} {goal[:80]}", "max_results": 3}))

        # Domain-specific tool routing
        if any(kw in domain_lower for kw in ["regulat", "compliance", "legal", "statutory", "licens"]):
            jurisdiction = "EU" if "eu" in goal.lower() or "gdpr" in goal.lower() else "US"
            if "brazil" in goal.lower() or "anatel" in goal.lower():
                jurisdiction = "BR"
            tool_selections.append(("regulatory_lookup", {
                "jurisdiction": jurisdiction,
                "domain": domain_lower.split()[0] if domain_lower.split() else "general",
                "query": goal[:100]
            }))

        if any(kw in domain_lower for kw in ["financ", "economic", "budget", "roi", "cost", "margin"]):
            tool_selections.append(("financial_calculator", {
                "calculation_type": "roi",
                "parameters": {"investment": 100000, "projected_revenue": 180000}
            }))

        if any(kw in domain_lower for kw in ["market", "demand", "customer", "competitive", "positioning"]):
            tool_selections.append(("market_data", {
                "market": goal[:60],
                "metric": "market_size"
            }))

        if any(kw in domain_lower for kw in ["risk", "safety", "operations", "sre", "reliability"]):
            tool_selections.append(("risk_assessment", {
                "scenario": goal[:100],
                "category": "operational"
            }))

        # Invoke selected tools (cap at 3 per agent)
        for tool_name, tool_args in tool_selections[:3]:
            result = await self.invoke_tool(
                tool_name=tool_name,
                arguments=tool_args,
                requesting_agent=agent_name,
                run_id=run_id
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
                        if k not in ("search_engine", "source"):
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
        by_tool = {}
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
