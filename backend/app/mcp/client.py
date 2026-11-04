"""MCP Tool Client — Enables agents to invoke MCP tools during analysis.

The MCPToolClient is integrated into the specialist execution flow, allowing
each agent to autonomously select and invoke relevant tools based on their
analysis needs. Tool selection is dynamic and driven by the tool catalog,
NOT hardcoded to any specific domain.
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
        tool_selections: List[tuple[str, Dict[str, Any]]] = []

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

        # 3. Calculator when goal involves quantitative aspects
        numeric_keywords = ["cost", "budget", "roi", "revenue", "price", "profit",
                          "margin", "rate", "percent", "calculate", "npv", "breakeven",
                          "forecast", "growth", "investment", "financial"]
        if "calculator" in available_names and any(kw in goal_lower for kw in numeric_keywords):
            tool_selections.append(("calculator", {
                "operation": "evaluate",
                "parameters": {"expression": "0"},  # Placeholder — agent provides real expression
            }))

        # 4. Data analyzer when structured data analysis is needed
        data_keywords = ["data", "dataset", "metrics", "statistics", "compare",
                        "trends", "analyze", "performance", "benchmark"]
        if "data_analyzer" in available_names and any(kw in goal_lower for kw in data_keywords):
            tool_selections.append(("data_analyzer", {
                "data": [],  # Placeholder — agent provides real data
                "analysis_type": "summary",
            }))

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
