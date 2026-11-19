"""MCP Protocol Types and Tool Registry.

Defines the Model Context Protocol (MCP) schema types used for tool
definitions, invocations, and results throughout CollaborAI.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("collaborai.mcp.protocol")


class MCPToolParameter(BaseModel):
    """Schema for a single tool parameter."""
    name: str = Field(description="Parameter name")
    type: Literal["string", "number", "boolean", "object", "array"] = Field(
        default="string", description="JSON Schema type"
    )
    description: str = Field(default="", description="What this parameter does")
    required: bool = Field(default=False, description="Whether this parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value if not required")


class MCPTool(BaseModel):
    """MCP Tool Definition following Model Context Protocol spec."""
    name: str = Field(description="Unique tool identifier e.g. 'web_search'")
    description: str = Field(description="Human-readable description of what this tool does")
    category: str = Field(
        default="general", description="Tool category for filtering (e.g. research, calculation, data_retrieval, analysis, system)"
    )
    parameters: List[MCPToolParameter] = Field(
        default_factory=list, description="Input parameter schema"
    )
    is_enabled: bool = Field(default=True, description="Whether tool is currently available")


class MCPToolCall(BaseModel):
    """A request to invoke an MCP tool."""
    call_id: str = Field(description="Unique invocation ID e.g. 'TC-abc123'")
    tool_name: str = Field(description="Name of the tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool input arguments")
    requesting_agent: str = Field(default="system", description="Agent requesting tool use")
    run_id: str = Field(default="", description="Associated deliberation run ID")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MCPToolResult(BaseModel):
    """Result returned from an MCP tool invocation."""
    call_id: str = Field(description="Matches the originating MCPToolCall.call_id")
    tool_name: str = Field(description="Tool that produced this result")
    status: Literal["success", "error", "timeout"] = Field(default="success")
    result: Any = Field(default=None, description="Structured result payload")
    error_message: Optional[str] = Field(default=None, description="Error details if status != success")
    execution_time_ms: float = Field(default=0.0, description="Tool execution wall time in ms")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Input arguments passed to the tool")
    requesting_agent: str = Field(default="system", description="Agent that invoked the tool")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Type alias for async tool handler functions
ToolHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, Any]]


class MCPToolRegistry:
    """Central registry of available MCP tools and their handlers."""

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
        self._handlers: Dict[str, ToolHandler] = {}

    def register(self, tool: MCPTool, handler: ToolHandler) -> None:
        """Register a tool definition and its async handler."""
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler
        logger.info("MCP tool registered: %s (%s)", tool.name, tool.category)

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Lookup a tool by name."""
        return self._tools.get(name)

    def get_handler(self, name: str) -> Optional[ToolHandler]:
        """Get the handler for a tool."""
        return self._handlers.get(name)

    def list_tools(self, category: Optional[str] = None, enabled_only: bool = True) -> List[MCPTool]:
        """List all registered tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.is_enabled]
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def list_tool_names(self) -> List[str]:
        """Return a list of all registered tool names."""
        return list(self._tools.keys())

    def tool_count(self) -> int:
        return len(self._tools)
