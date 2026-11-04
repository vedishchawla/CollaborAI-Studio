"""MCP Tools API Routes for CollaborAI.

Exposes endpoints for listing MCP tools, invoking them, and retrieving
tool invocation history for a specific deliberation run.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..mcp.protocol import MCPTool, MCPToolResult
from ..mcp.client import MCPToolClient
from ..mcp.tools import create_default_registry
from ..orchestration.runner import orchestrator

router = APIRouter(prefix="/api/mcp", tags=["MCP Tools"])

# Shared registry and client
_registry = create_default_registry()


class MCPToolListResponse(BaseModel):
    tools: List[MCPTool]
    total_count: int


class MCPInvokeRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    requesting_agent: str = "manual"
    run_id: str = ""


class MCPInvokeResponse(BaseModel):
    result: MCPToolResult


class MCPRunToolsResponse(BaseModel):
    run_id: str
    mcp_tools_used: List[Dict[str, Any]]
    total_invocations: int


@router.get("/tools", response_model=MCPToolListResponse)
async def list_mcp_tools(category: Optional[str] = None):
    """List all available MCP tools in the CollaborAI system."""
    tools = _registry.list_tools(category=category)
    return MCPToolListResponse(tools=tools, total_count=len(tools))


@router.get("/tools/{tool_name}", response_model=MCPTool)
async def get_mcp_tool(tool_name: str):
    """Get details of a specific MCP tool."""
    tool = _registry.get_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return tool


@router.post("/invoke", response_model=MCPInvokeResponse)
async def invoke_mcp_tool(req: MCPInvokeRequest):
    """Manually invoke an MCP tool (for testing or external use)."""
    client = MCPToolClient(registry=_registry)
    result = await client.invoke_tool(
        tool_name=req.tool_name,
        arguments=req.arguments,
        requesting_agent=req.requesting_agent,
        run_id=req.run_id,
    )
    if result.status == "error" and "not found" in (result.error_message or ""):
        raise HTTPException(status_code=404, detail=result.error_message)
    return MCPInvokeResponse(result=result)


@router.get("/runs/{run_id}/tools", response_model=MCPRunToolsResponse)
async def get_run_tool_usage(run_id: str):
    """Get MCP tool usage summary for a specific deliberation run."""
    state = orchestrator.get_state(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Run not found")

    mcp_data = getattr(state, "mcp_tool_calls", [])
    return MCPRunToolsResponse(
        run_id=run_id,
        mcp_tools_used=[call if isinstance(call, dict) else call.model_dump() for call in mcp_data],
        total_invocations=len(mcp_data),
    )
