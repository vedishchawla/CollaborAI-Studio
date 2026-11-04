"""MCP (Model Context Protocol) Tools Module for CollaborAI.

Provides an MCP-compliant tool server and client integration that enables
specialist agents to invoke external tools during analysis, and exposes
CollaborAI capabilities as MCP tools for external consumers.
"""

from .protocol import MCPTool, MCPToolCall, MCPToolResult, MCPToolRegistry
from .server import MCPToolServer
from .client import MCPToolClient
from .tools import BUILTIN_TOOLS

__all__ = [
    "MCPTool",
    "MCPToolCall",
    "MCPToolResult", 
    "MCPToolRegistry",
    "MCPToolServer",
    "MCPToolClient",
    "BUILTIN_TOOLS",
]
