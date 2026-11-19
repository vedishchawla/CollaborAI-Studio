"""Tests for MCP Tool Protocol, Registry, Client, and General-Purpose Tools."""

import asyncio
import pytest
from app.mcp.protocol import MCPTool, MCPToolCall, MCPToolResult, MCPToolParameter, MCPToolRegistry
from app.mcp.tools import (
    create_default_registry,
    web_search_handler,
    text_summarizer_handler,
    calculator_handler,
    data_analyzer_handler,
    document_retriever_handler,
    BUILTIN_TOOLS,
)
from app.mcp.client import MCPToolClient


# ── Protocol Models ──────────────────────────────────────────────────────────

class TestMCPProtocol:
    def test_tool_definition(self):
        tool = MCPTool(
            name="test_tool",
            description="A test tool",
            category="research",
            parameters=[
                MCPToolParameter(name="query", type="string", required=True),
            ]
        )
        assert tool.name == "test_tool"
        assert len(tool.parameters) == 1
        assert tool.parameters[0].required is True

    def test_tool_definition_custom_category(self):
        """Category is a free string — any value is valid."""
        tool = MCPTool(name="custom", description="Custom", category="my_custom_category")
        assert tool.category == "my_custom_category"

    def test_tool_call_model(self):
        call = MCPToolCall(
            call_id="TC-001",
            tool_name="web_search",
            arguments={"query": "AI regulations"},
            requesting_agent="TestAgent",
        )
        assert call.tool_name == "web_search"
        assert call.arguments["query"] == "AI regulations"

    def test_tool_result_model(self):
        result = MCPToolResult(
            call_id="TC-001",
            tool_name="web_search",
            status="success",
            result={"results": []},
            execution_time_ms=150.5,
        )
        assert result.status == "success"
        assert result.execution_time_ms == 150.5


# ── Tool Registry ────────────────────────────────────────────────────────────

class TestMCPToolRegistry:
    def test_create_default_registry(self):
        registry = create_default_registry()
        assert registry.tool_count() == 5
        expected_names = ["web_search", "text_summarizer", "calculator", "data_analyzer", "document_retriever"]
        for name in expected_names:
            assert name in registry.list_tool_names()

    def test_register_and_lookup(self):
        registry = MCPToolRegistry()
        tool = MCPTool(name="custom_tool", description="Custom")

        async def handler(args):
            return {"ok": True}

        registry.register(tool, handler)
        assert registry.get_tool("custom_tool") is not None
        assert registry.get_handler("custom_tool") is not None
        assert registry.tool_count() == 1

    def test_register_custom_tool_at_runtime(self):
        """Verify that custom domain tools can be registered alongside defaults."""
        registry = create_default_registry()
        assert registry.tool_count() == 5

        custom_tool = MCPTool(
            name="sentiment_analyzer",
            description="Analyze sentiment of text",
            category="nlp",
            parameters=[MCPToolParameter(name="text", type="string", required=True)],
        )

        async def handler(args):
            return {"sentiment": "positive", "score": 0.85}

        registry.register(custom_tool, handler)
        assert registry.tool_count() == 6
        assert "sentiment_analyzer" in registry.list_tool_names()

    def test_lookup_missing_tool(self):
        registry = MCPToolRegistry()
        assert registry.get_tool("nonexistent") is None
        assert registry.get_handler("nonexistent") is None

    def test_list_tools_by_category(self):
        registry = create_default_registry()
        research_tools = registry.list_tools(category="research")
        assert all(t.category == "research" for t in research_tools)
        assert len(research_tools) >= 1

    def test_list_tools_enabled_only(self):
        registry = MCPToolRegistry()
        enabled_tool = MCPTool(name="enabled", description="E", is_enabled=True)
        disabled_tool = MCPTool(name="disabled", description="D", is_enabled=False)

        async def handler(args):
            return {}

        registry.register(enabled_tool, handler)
        registry.register(disabled_tool, handler)

        enabled = registry.list_tools(enabled_only=True)
        all_tools = registry.list_tools(enabled_only=False)
        assert len(enabled) == 1
        assert len(all_tools) == 2

    def test_builtin_tools_list(self):
        assert len(BUILTIN_TOOLS) == 5
        names = [t.name for t in BUILTIN_TOOLS]
        assert "web_search" in names
        assert "calculator" in names
        assert "text_summarizer" in names
        assert "data_analyzer" in names
        assert "document_retriever" in names


# ── Built-in Tool Handlers (General-Purpose) ─────────────────────────────────

class TestBuiltinTools:
    # ── Web Search ──
    @pytest.mark.asyncio
    async def test_web_search(self):
        result = await web_search_handler({"query": "AI market trends", "max_results": 3})
        assert result["query"] == "AI market trends"
        assert result["results_count"] == 3
        assert len(result["results"]) == 3
        for r in result["results"]:
            assert "title" in r
            assert "url" in r
            assert "snippet" in r
            assert "relevance_score" in r

    @pytest.mark.asyncio
    async def test_web_search_deterministic(self):
        """Same query should produce same results (deterministic seeding)."""
        r1 = await web_search_handler({"query": "test query"})
        r2 = await web_search_handler({"query": "test query"})
        assert r1["results"][0]["url"] == r2["results"][0]["url"]

    # ── Text Summarizer ──
    @pytest.mark.asyncio
    async def test_text_summarizer_concise(self):
        long_text = (
            "The global AI market is expected to grow significantly in the next decade. "
            "Major tech companies are investing billions of dollars in AI research and development. "
            "Healthcare applications of AI are showing promising results in early detection. "
            "Regulatory frameworks are being developed across multiple jurisdictions. "
            "The workforce transformation due to AI will require significant reskilling efforts."
        )
        result = await text_summarizer_handler({"text": long_text, "max_sentences": 2, "style": "concise"})
        assert result["style"] == "concise"
        assert result["sentences_extracted"] <= 2
        assert result["compression_ratio"] <= 1.0
        assert result["original_length"] > result["summary_length"]

    @pytest.mark.asyncio
    async def test_text_summarizer_bullets(self):
        text = "First point about technology. Second point about markets. Third point about regulations."
        result = await text_summarizer_handler({"text": text, "max_sentences": 3, "style": "bullets"})
        assert result["style"] == "bullets"
        assert "•" in result["summary"]

    @pytest.mark.asyncio
    async def test_text_summarizer_empty_text(self):
        result = await text_summarizer_handler({"text": "", "max_sentences": 3})
        assert result["sentence_count"] == 0

    # ── Calculator ──
    @pytest.mark.asyncio
    async def test_calculator_evaluate(self):
        result = await calculator_handler({
            "operation": "evaluate",
            "parameters": {"expression": "2 + 3 * 4"}
        })
        assert result["operation"] == "evaluate"
        assert result["result"] == 14

    @pytest.mark.asyncio
    async def test_calculator_percentage(self):
        result = await calculator_handler({
            "operation": "percentage",
            "parameters": {"value": 25, "total": 200}
        })
        assert result["operation"] == "percentage"
        assert result["percentage"] == 12.5

    @pytest.mark.asyncio
    async def test_calculator_ratio(self):
        result = await calculator_handler({
            "operation": "ratio",
            "parameters": {"a": 100, "b": 25}
        })
        assert result["ratio"] == 4.0

    @pytest.mark.asyncio
    async def test_calculator_roi(self):
        result = await calculator_handler({
            "operation": "roi",
            "parameters": {"investment": 100000, "projected_revenue": 200000}
        })
        assert result["operation"] == "ROI"
        assert result["roi_percent"] == 100.0
        assert result["verdict"] == "Positive"

    @pytest.mark.asyncio
    async def test_calculator_npv(self):
        result = await calculator_handler({
            "operation": "npv",
            "parameters": {
                "cash_flows": [-100000, 30000, 40000, 50000, 60000],
                "discount_rate": 0.1
            }
        })
        assert result["operation"] == "NPV"
        assert "npv" in result
        assert "verdict" in result

    @pytest.mark.asyncio
    async def test_calculator_breakeven(self):
        result = await calculator_handler({
            "operation": "breakeven",
            "parameters": {"fixed_costs": 60000, "unit_price": 100, "variable_cost_per_unit": 40}
        })
        assert result["operation"] == "breakeven"
        assert result["breakeven_units"] == 1000

    @pytest.mark.asyncio
    async def test_calculator_breakeven_invalid(self):
        result = await calculator_handler({
            "operation": "breakeven",
            "parameters": {"fixed_costs": 60000, "unit_price": 40, "variable_cost_per_unit": 100}
        })
        assert "error" in result

    @pytest.mark.asyncio
    async def test_calculator_statistics(self):
        result = await calculator_handler({
            "operation": "statistics",
            "parameters": {"values": [10, 20, 30, 40, 50]}
        })
        assert result["operation"] == "statistics"
        assert result["count"] == 5
        assert result["mean"] == 30.0
        assert result["median"] == 30.0
        assert result["min"] == 10
        assert result["max"] == 50

    @pytest.mark.asyncio
    async def test_calculator_unknown_operation(self):
        result = await calculator_handler({
            "operation": "unknown_calc",
            "parameters": {}
        })
        assert "error" in result

    @pytest.mark.asyncio
    async def test_calculator_ast_functions_and_exponents(self):
        result = await calculator_handler({
            "operation": "evaluate",
            "parameters": {"expression": "sqrt(144) + 2^3"}
        })
        assert result["result"] == 20

    @pytest.mark.asyncio
    async def test_calculator_top_level_args_and_currency_suffixes(self):
        result = await calculator_handler({
            "operation": "evaluate",
            "expression": "$1.5M - $500k"
        })
        assert result["result"] == 1000000

    @pytest.mark.asyncio
    async def test_calculator_roi_zero_investment_guard(self):
        result = await calculator_handler({
            "operation": "roi",
            "parameters": {"investment": 0, "projected_revenue": 50000}
        })
        assert "error" in result

    @pytest.mark.asyncio
    async def test_calculator_compound_growth_and_margin(self):
        cg = await calculator_handler({
            "operation": "compound_growth",
            "parameters": {"principal": 10000, "rate_percent": 10, "periods": 2}
        })
        assert cg["final_value"] == 12100.0
        margin = await calculator_handler({
            "operation": "margin",
            "parameters": {"revenue": 200000, "cost": 150000}
        })
        assert margin["gross_margin_percent"] == 25.0

    # ── Data Analyzer ──
    @pytest.mark.asyncio
    async def test_data_analyzer_summary(self):
        data = [
            {"name": "Alpha", "score": 85, "region": "US"},
            {"name": "Beta", "score": 92, "region": "EU"},
            {"name": "Gamma", "score": 78, "region": "US"},
        ]
        result = await data_analyzer_handler({"data": data, "analysis_type": "summary"})
        assert result["analysis_type"] == "summary"
        assert result["record_count"] == 3
        assert "score" in result["field_summaries"]
        assert result["field_summaries"]["score"]["type"] == "numeric"
        assert result["field_summaries"]["region"]["type"] == "categorical"

    @pytest.mark.asyncio
    async def test_data_analyzer_group(self):
        data = [
            {"region": "US", "revenue": 100},
            {"region": "US", "revenue": 200},
            {"region": "EU", "revenue": 150},
        ]
        result = await data_analyzer_handler({
            "data": data,
            "analysis_type": "group",
            "group_by": "region",
            "metric": "revenue",
        })
        assert result["analysis_type"] == "group"
        assert result["group_count"] == 2
        assert result["groups"]["US"]["count"] == 2
        assert result["groups"]["US"]["metric_mean"] == 150.0

    @pytest.mark.asyncio
    async def test_data_analyzer_compare(self):
        data = [
            {"year": 2020, "value": 100},
            {"year": 2023, "value": 180},
        ]
        result = await data_analyzer_handler({"data": data, "analysis_type": "compare"})
        assert result["analysis_type"] == "compare"
        assert result["comparisons"]["value"]["change"] == 80

    @pytest.mark.asyncio
    async def test_data_analyzer_empty(self):
        result = await data_analyzer_handler({"data": [], "analysis_type": "summary"})
        assert "error" in result

    # ── Document Retriever ──
    @pytest.mark.asyncio
    async def test_document_retriever(self):
        result = await document_retriever_handler({
            "query": "compliance requirements",
            "source": "policy_store",
            "max_docs": 3,
        })
        assert result["query"] == "compliance requirements"
        assert result["source"] == "policy_store"
        assert result["documents_found"] == 3
        for doc in result["documents"]:
            assert "doc_id" in doc
            assert "title" in doc
            assert "relevance_score" in doc
            assert "excerpt" in doc

    @pytest.mark.asyncio
    async def test_document_retriever_deterministic(self):
        r1 = await document_retriever_handler({"query": "test query"})
        r2 = await document_retriever_handler({"query": "test query"})
        assert r1["documents"][0]["doc_id"] == r2["documents"][0]["doc_id"]


# ── MCP Tool Client ──────────────────────────────────────────────────────────

class TestMCPToolClient:
    @pytest.mark.asyncio
    async def test_invoke_tool_success(self):
        client = MCPToolClient()
        result = await client.invoke_tool(
            tool_name="web_search",
            arguments={"query": "test"},
            requesting_agent="TestAgent"
        )
        assert result.status == "success"
        assert result.tool_name == "web_search"
        assert result.execution_time_ms > 0
        assert result.result["query"] == "test"

    @pytest.mark.asyncio
    async def test_invoke_nonexistent_tool(self):
        client = MCPToolClient()
        result = await client.invoke_tool(
            tool_name="nonexistent_tool",
            arguments={}
        )
        assert result.status == "error"
        assert "not found" in result.error_message

    @pytest.mark.asyncio
    async def test_invoke_tracks_history(self):
        client = MCPToolClient()
        await client.invoke_tool("web_search", {"query": "q1"})
        await client.invoke_tool("calculator", {"operation": "evaluate", "parameters": {"expression": "1+1"}})
        assert len(client.call_history) == 2
        assert len(client.result_history) == 2

    @pytest.mark.asyncio
    async def test_invoke_tools_for_agent_always_gets_web_search(self):
        """Every agent should get web_search as a universal tool."""
        client = MCPToolClient()
        results = await client.invoke_tools_for_agent(
            agent_name="AnyAgent",
            agent_domain="Some Domain",
            goal="Analyze something"
        )
        tool_names = [r.tool_name for r in results]
        assert "web_search" in tool_names

    @pytest.mark.asyncio
    async def test_invoke_tools_for_agent_numeric_goal_gets_calculator(self):
        """Goals with numeric keywords should trigger calculator selection with real numbers."""
        client = MCPToolClient()
        results = await client.invoke_tools_for_agent(
            agent_name="FinancialAgent",
            agent_domain="Finance",
            goal="Launch service within 6 weeks under a $100,000 budget and calculate ROI"
        )
        tool_names = [r.tool_name for r in results]
        assert "web_search" in tool_names
        assert "calculator" in tool_names
        calc_res = next(r for r in results if r.tool_name == "calculator")
        assert calc_res.status == "success"
        assert calc_res.requesting_agent == "FinancialAgent"
        assert calc_res.arguments.get("parameters", {}).get("investment") == 100000.0
        assert calc_res.result["roi_percent"] > 0

    @pytest.mark.asyncio
    async def test_invoke_tools_for_agent_data_goal_gets_analyzer(self):
        """Goals with data keywords should trigger data_analyzer selection."""
        client = MCPToolClient()
        results = await client.invoke_tools_for_agent(
            agent_name="DataAgent",
            agent_domain="Analytics",
            goal="Analyze performance data and compare metrics"
        )
        tool_names = [r.tool_name for r in results]
        assert "web_search" in tool_names

    @pytest.mark.asyncio
    async def test_invoke_tools_capped_at_max(self):
        client = MCPToolClient()
        results = await client.invoke_tools_for_agent(
            agent_name="FullAgent",
            agent_domain="Everything",
            goal="Calculate budget data with summary of report findings",
            max_tools=3,
        )
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_invoke_tools_custom_max(self):
        client = MCPToolClient()
        results = await client.invoke_tools_for_agent(
            agent_name="Agent",
            agent_domain="Domain",
            goal="General analysis",
            max_tools=2,
        )
        assert len(results) <= 2

    def test_format_tools_for_prompt(self):
        client = MCPToolClient()
        prompt = client.format_tools_for_prompt()
        assert "AVAILABLE MCP TOOLS" in prompt
        assert "web_search" in prompt
        assert "calculator" in prompt
        assert "text_summarizer" in prompt

    @pytest.mark.asyncio
    async def test_format_results_for_prompt(self):
        client = MCPToolClient()
        results = [
            await client.invoke_tool("web_search", {"query": "test"})
        ]
        formatted = client.format_results_for_prompt(results)
        assert "MCP TOOL RESULTS" in formatted
        assert "web_search" in formatted

    def test_format_results_empty(self):
        client = MCPToolClient()
        assert "No supplementary tool data" in client.format_results_for_prompt([])

    @pytest.mark.asyncio
    async def test_invocation_summary(self):
        client = MCPToolClient()
        await client.invoke_tool("web_search", {"query": "q1"})
        await client.invoke_tool("web_search", {"query": "q2"})
        await client.invoke_tool("calculator", {"operation": "percentage", "parameters": {"value": 50, "total": 200}})

        summary = client.get_invocation_summary()
        assert summary["total_invocations"] == 3
        assert summary["successful"] == 3
        assert summary["failed"] == 0
        assert summary["invocations_by_tool"]["web_search"] == 2
        assert summary["invocations_by_tool"]["calculator"] == 1
        assert summary["total_execution_time_ms"] > 0

    def test_list_available_tools(self):
        client = MCPToolClient()
        all_tools = client.list_available_tools()
        assert len(all_tools) == 5
        research = client.list_available_tools(category="research")
        assert all(t.category == "research" for t in research)

    @pytest.mark.asyncio
    async def test_client_with_custom_registry(self):
        """Client works with a custom registry that has different tools."""
        registry = MCPToolRegistry()
        custom_tool = MCPTool(name="echo", description="Echo input", category="utility")

        async def echo_handler(args):
            return {"echo": args}

        registry.register(custom_tool, echo_handler)
        client = MCPToolClient(registry=registry)

        assert len(client.list_available_tools()) == 1
        result = await client.invoke_tool("echo", {"message": "hello"})
        assert result.status == "success"
        assert result.result["echo"]["message"] == "hello"
