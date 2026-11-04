import React, { useState, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import {
  Wrench,
  Search,
  FileText,
  Calculator,
  BarChart2,
  BookOpen,
  CheckCircle2,
  XCircle,
  Clock,
  Play,
  Cpu,
  ChevronDown,
  ChevronRight,
  Database,
  Terminal,
} from 'lucide-react';
import { MCPTool, MCPToolResult } from '@/types/schema';
import { fetchMCPTools, invokeMCPTool } from '@/services/api';

interface MCPPanelProps {
  toolCalls: any[];
  toolsSummary?: Record<string, any> | undefined;
  currentRunId?: string | null;
}

/**
 * Map a tool's category to a suitable icon. Since tools are general-purpose
 * and registered dynamically, the mapping is by category, not by name.
 */
const getCategoryIcon = (category: string) => {
  switch (category) {
    case 'research':
      return <Search className="w-4 h-4 text-cyan-400" />;
    case 'analysis':
      return <BarChart2 className="w-4 h-4 text-purple-400" />;
    case 'calculation':
      return <Calculator className="w-4 h-4 text-emerald-400" />;
    case 'data_retrieval':
      return <Database className="w-4 h-4 text-amber-400" />;
    case 'system':
      return <Terminal className="w-4 h-4 text-rose-400" />;
    default:
      return <Wrench className="w-4 h-4 text-blue-400" />;
  }
};

/**
 * Generate a placeholder JSON arguments template from a tool's parameter schema.
 * This makes the sandbox work with ANY registered tool, not just built-in ones.
 */
const generateArgsTemplate = (tool: MCPTool): string => {
  const args: Record<string, any> = {};
  for (const p of tool.parameters) {
    if (p.type === 'string') args[p.name] = p.default ?? (p.required ? '<required>' : '');
    else if (p.type === 'number') args[p.name] = p.default ?? 0;
    else if (p.type === 'boolean') args[p.name] = p.default ?? true;
    else if (p.type === 'object') args[p.name] = p.default ?? {};
    else if (p.type === 'array') args[p.name] = p.default ?? [];
    else args[p.name] = p.default ?? null;
  }
  return JSON.stringify(args, null, 2);
};

export const MCPPanel: React.FC<MCPPanelProps> = ({
  toolCalls = [],
  toolsSummary,
  currentRunId,
}) => {
  const [availableTools, setAvailableTools] = useState<MCPTool[]>([]);
  const [selectedTool, setSelectedTool] = useState<string>('');
  const [toolArgs, setToolArgs] = useState<string>('{}');
  const [isInvoking, setIsInvoking] = useState(false);
  const [manualResult, setManualResult] = useState<MCPToolResult | null>(null);
  const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<'invocations' | 'catalog' | 'test'>('invocations');

  // Load available MCP tools from the catalog API
  useEffect(() => {
    fetchMCPTools()
      .then((data) => {
        const tools = data.tools || [];
        setAvailableTools(tools);
        // Auto-select the first tool if none is selected
        if (tools.length > 0 && !selectedTool) {
          const firstTool = tools[0]!;
          setSelectedTool(firstTool.name);
          setToolArgs(generateArgsTemplate(firstTool));
        }
      })
      .catch((err) => console.error('Failed to load MCP tools:', err));
  }, []);

  // Build a lookup map for quick tool access
  const toolMap = useMemo(
    () => Object.fromEntries(availableTools.map((t) => [t.name, t])),
    [availableTools],
  );

  const handleToolSelect = (toolName: string) => {
    setSelectedTool(toolName);
    const tool = toolMap[toolName] as MCPTool | undefined;
    if (tool) {
      setToolArgs(generateArgsTemplate(tool));
    } else {
      setToolArgs('{}');
    }
  };

  const handleManualInvoke = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsInvoking(true);
    setManualResult(null);
    try {
      let parsedArgs = {};
      try {
        parsedArgs = JSON.parse(toolArgs);
      } catch (e) {
        alert('Invalid JSON in arguments field');
        setIsInvoking(false);
        return;
      }
      const res = await invokeMCPTool({
        tool_name: selectedTool,
        arguments: parsedArgs,
        requesting_agent: 'HumanTester',
        run_id: currentRunId || 'manual-session',
      });
      setManualResult(res);
    } catch (err: any) {
      alert(`Tool execution failed: ${err.message}`);
    } finally {
      setIsInvoking(false);
    }
  };

  /** Resolve icon for a tool name — uses category from catalog, falls back to generic. */
  const getToolIcon = (name: string) => {
    const tool = toolMap[name];
    return tool ? getCategoryIcon(tool.category) : <Wrench className="w-4 h-4 text-blue-400" />;
  };

  return (
    <div className="space-y-4">
      {/* Experiment Header Banner */}
      <div className="p-3.5 rounded-lg border border-primary/20 bg-primary/5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase bg-primary/20 text-primary border border-primary/30">
          </span>
          <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-primary" />
            Model Context Protocol (MCP) Multi-Agent Tool Integration
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          <span>Active Tools: <strong className="text-foreground">{availableTools.length}</strong></span>
          <span>•</span>
          <span>Invocations: <strong className="text-foreground">{toolCalls.length}</strong></span>
          {toolsSummary?.['total_execution_time_ms'] && (
            <>
              <span>•</span>
              <span>Avg Latency: <strong className="text-foreground">{Math.round(toolsSummary['total_execution_time_ms'] / (toolCalls.length || 1))}ms</strong></span>
            </>
          )}
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="flex items-center gap-2 border-b border-border pb-2">
        <button
          onClick={() => setActiveSubTab('invocations')}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeSubTab === 'invocations'
              ? 'bg-muted text-foreground border border-border shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Agent Tool Invocations ({toolCalls.length})
        </button>
        <button
          onClick={() => setActiveSubTab('catalog')}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeSubTab === 'catalog'
              ? 'bg-muted text-foreground border border-border shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          MCP Tool Catalog ({availableTools.length})
        </button>
        <button
          onClick={() => setActiveSubTab('test')}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeSubTab === 'test'
              ? 'bg-muted text-foreground border border-border shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Interactive Tool Sandbox
        </button>
      </div>

      {/* ── Subtab 1: Invocations Live Feed ── */}
      {activeSubTab === 'invocations' && (
        <div className="space-y-2.5">
          {toolCalls.length === 0 ? (
            <div className="p-8 text-center rounded-lg border border-dashed border-border bg-muted/20">
              <Database className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-60" />
              <p className="text-xs font-medium text-foreground">No MCP tools invoked yet in this deliberation.</p>
              <p className="text-[11px] text-muted-foreground mt-1">
                When agents analyze the goal, they dynamically select and invoke registered MCP tools to ground their assertions in external evidence.
              </p>
            </div>
          ) : (
            toolCalls.map((call, idx) => {
              const isExpanded = expandedCallId === (call.call_id || idx.toString());
              const toolName = call.tool_name || 'mcp_tool';
              const agentName = call.requesting_agent || 'Specialist';
              const isSuccess = call.status === 'success' || !call.error_message;

              return (
                <div
                  key={call.call_id || idx}
                  className="rounded-lg border border-border bg-card/60 p-3 text-xs transition-all hover:border-primary/30"
                >
                  <div
                    className="flex items-center justify-between cursor-pointer gap-2"
                    onClick={() => setExpandedCallId(isExpanded ? null : (call.call_id || idx.toString()))}
                  >
                    <div className="flex items-center gap-2">
                      {getToolIcon(toolName)}
                      <span className="font-mono font-bold text-foreground">{toolName}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border">
                        by {agentName}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {call.execution_time_ms && (
                        <span className="text-[10px] font-mono text-muted-foreground flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {Math.round(call.execution_time_ms)}ms
                        </span>
                      )}
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 ${
                          isSuccess
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                        }`}
                      >
                        {isSuccess ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        {isSuccess ? 'Success' : 'Error'}
                      </span>
                      {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-3 pt-3 border-t border-border/60 space-y-2">
                      {call.arguments && (
                        <div>
                          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
                            Arguments Passed:
                          </span>
                          <pre className="p-2 rounded bg-muted text-[11px] font-mono text-foreground overflow-x-auto">
                            {JSON.stringify(call.arguments, null, 2)}
                          </pre>
                        </div>
                      )}

                      <div>
                        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
                          Tool Output Result:
                        </span>
                        <pre className="p-2 rounded bg-muted text-[11px] font-mono text-foreground overflow-x-auto max-h-48">
                          {JSON.stringify(call.result || call.data || call, null, 2)}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ── Subtab 2: Tool Catalog (fully dynamic from API) ── */}
      {activeSubTab === 'catalog' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {availableTools.map((tool) => (
            <div
              key={tool.name}
              className="p-3.5 rounded-lg border border-border bg-card/60 space-y-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getCategoryIcon(tool.category)}
                  <span className="font-mono font-bold text-xs text-foreground">{tool.name}</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border">
                  {tool.category}
                </span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {tool.description}
              </p>
              <div className="pt-2 border-t border-border/40">
                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block mb-1">
                  Parameters ({tool.parameters.length}):
                </span>
                <div className="flex flex-wrap gap-1">
                  {tool.parameters.map((p) => (
                    <span
                      key={p.name}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-muted/80 text-foreground border border-border"
                      title={`${p.description} (${p.type})${p.required ? ' - Required' : ''}`}
                    >
                      {p.name}: <span className="text-primary">{p.type}</span>
                      {p.required && <span className="text-rose-400">*</span>}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Subtab 3: Interactive Sandbox (dynamic tool list from catalog) ── */}
      {activeSubTab === 'test' && (
        <div className="p-4 rounded-lg border border-border bg-card/60 space-y-4 text-xs">
          <div className="flex items-center gap-2 pb-2 border-b border-border">
            <Terminal className="w-4 h-4 text-primary" />
            <span className="font-bold text-foreground">Interactive MCP Tool Test Console</span>
            <span className="text-[11px] text-muted-foreground ml-auto">
              Manually invoke any registered MCP tool outside the agent loop
            </span>
          </div>

          <form onSubmit={handleManualInvoke} className="space-y-3">
            <div>
              <label className="text-[11px] font-semibold text-muted-foreground block mb-1">
                Select Tool:
              </label>
              <div className="flex flex-wrap gap-2">
                {availableTools.map((tool) => (
                  <button
                    key={tool.name}
                    type="button"
                    onClick={() => handleToolSelect(tool.name)}
                    className={`px-2.5 py-1 rounded text-xs font-mono font-medium border transition-all flex items-center gap-1.5 ${
                      selectedTool === tool.name
                        ? 'bg-primary/20 border-primary text-primary'
                        : 'bg-muted border-border text-muted-foreground hover:text-foreground'
                    }`}
                    title={tool.description}
                  >
                    {getCategoryIcon(tool.category)}
                    {tool.name}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-[11px] font-semibold text-muted-foreground block mb-1">
                Arguments (JSON):
              </label>
              <textarea
                value={toolArgs}
                onChange={(e) => setToolArgs(e.target.value)}
                rows={5}
                className="w-full p-2.5 rounded bg-muted border border-border font-mono text-[11px] text-foreground focus:border-primary outline-none"
              />
            </div>

            <Button
              type="submit"
              disabled={isInvoking || !selectedTool}
              className="flex items-center gap-2 text-xs font-semibold"
            >
              <Play className="w-3.5 h-3.5" />
              {isInvoking ? 'Executing via MCP...' : 'Invoke Tool'}
            </Button>
          </form>

          {manualResult && (
            <div className="mt-4 pt-3 border-t border-border space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Invocation Output ({Math.round(manualResult.execution_time_ms)}ms)
                </span>
                <span className="text-[10px] font-mono text-muted-foreground">ID: {manualResult.call_id}</span>
              </div>
              <pre className="p-3 rounded bg-muted text-[11px] font-mono text-foreground overflow-x-auto max-h-60">
                {JSON.stringify(manualResult.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
