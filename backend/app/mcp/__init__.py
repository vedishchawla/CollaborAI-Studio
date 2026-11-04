"""MCP (Model Context Protocol) Tools Module for CollaborAI.

Provides general-purpose MCP tools that any specialist agent can invoke
during analysis, plus a dynamic registry for registering custom tools
at runtime. Tools are domain-agnostic by design.
"""

from .protocol import MCPTool, MCPToolCall, MCPToolResult, MCPToolRegistry
from .client import MCPToolClient
from .tools import BUILTIN_TOOLS

__all__ = [
    "MCPTool",
    "MCPToolCall",
    "MCPToolResult",
    "MCPToolRegistry",
    "MCPToolClient",
    "BUILTIN_TOOLS",
]
