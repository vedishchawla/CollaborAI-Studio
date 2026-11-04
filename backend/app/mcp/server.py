"""MCP Tool Server — Exposes CollaborAI capabilities as MCP tools.

Provides a FastAPI-based MCP-compliant server that external agents or
orchestrators can use to interact with the CollaborAI system.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .protocol import MCPTool, MCPToolCall, MCPToolResult, MCPToolRegistry
from .tools import create_default_registry

logger = logging.getLogger("collaborai.mcp.server")


class MCPListToolsResponse(BaseModel):
    """Response for listing available MCP tools."""
    tools: List[MCPTool]
    total_count: int


class MCPInvokeRequest(BaseModel):
    """Request to invoke an MCP tool."""
    tool_name: str = Field(description="Name of the tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    requesting_agent: str = Field(default="external", description="Requesting agent identifier")
    run_id: str = Field(default="", description="Optional associated run ID")


class MCPInvokeResponse(BaseModel):
    """Response from an MCP tool invocation."""
    result: MCPToolResult


class MCPToolServer:
    """FastAPI router exposing MCP tool endpoints."""

    def __init__(self, registry: Optional[MCPToolRegistry] = None):
        self.registry = registry or create_default_registry()
        self.router = APIRouter(prefix="/api/mcp", tags=["MCP Tools"])
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.router.get("/tools", response_model=MCPListToolsResponse)
        async def list_tools(category: Optional[str] = None):
            """List all available MCP tools."""
            tools = self.registry.list_tools(category=category)
            return MCPListToolsResponse(tools=tools, total_count=len(tools))

        @self.router.get("/tools/{tool_name}", response_model=MCPTool)
        async def get_tool(tool_name: str):
            """Get details of a specific MCP tool."""
            tool = self.registry.get_tool(tool_name)
            if not tool:
                raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
            return tool

        @self.router.post("/invoke", response_model=MCPInvokeResponse)
        async def invoke_tool(req: MCPInvokeRequest):
            """Invoke an MCP tool with the given arguments."""
            from .client import MCPToolClient
            client = MCPToolClient(registry=self.registry)
            result = await client.invoke_tool(
                tool_name=req.tool_name,
                arguments=req.arguments,
                requesting_agent=req.requesting_agent,
                run_id=req.run_id
            )
            if result.status == "error" and "not found" in (result.error_message or ""):
                raise HTTPException(status_code=404, detail=result.error_message)
            return MCPInvokeResponse(result=result)
