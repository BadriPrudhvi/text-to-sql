"use client";

import { useMemo, useState } from "react";
import { ChevronRight, Search, Table2, Columns3 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { SchemaTable } from "@/hooks/use-schema";

interface SchemaBrowserProps {
  tables: SchemaTable[];
  isLoading: boolean;
  onTableClick?: (tableName: string) => void;
}

interface TableGroup {
  prefix: string;
  tables: SchemaTable[];
}

function groupTables(tables: SchemaTable[]): TableGroup[] {
  const hasPrefixes = tables.some((t) => t.name.includes("."));
  if (!hasPrefixes) {
    return [{ prefix: "", tables }];
  }

  const groups = new Map<string, SchemaTable[]>();
  for (const table of tables) {
    const dotIdx = table.name.indexOf(".");
    const prefix = dotIdx > 0 ? table.name.slice(0, dotIdx) : "";
    if (!groups.has(prefix)) groups.set(prefix, []);
    groups.get(prefix)!.push(table);
  }

  return Array.from(groups.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([prefix, tbls]) => ({ prefix, tables: tbls }));
}

export function SchemaBrowser({ tables, isLoading, onTableClick }: SchemaBrowserProps) {
  const [search, setSearch] = useState("");
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    if (!search.trim()) return tables;
    const q = search.toLowerCase();
    return tables.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.description?.toLowerCase().includes(q) ||
        t.columns.some((c) => c.name.toLowerCase().includes(q))
    );
  }, [tables, search]);

  const groups = useMemo(() => groupTables(filtered), [filtered]);

  const toggleTable = (name: string) => {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const toggleGroup = (prefix: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(prefix)) next.delete(prefix);
      else next.add(prefix);
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="px-2 py-3 text-xs text-sidebar-foreground/50 text-center">
        Loading schema...
      </div>
    );
  }

  if (tables.length === 0) return null;

  return (
    <div className="space-y-1.5">
      {/* Search */}
      <div className="relative px-2">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-3 w-3 text-sidebar-foreground/40" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search tables..."
          className="w-full rounded-md border border-sidebar-border bg-sidebar py-1.5 pl-7 pr-2 text-xs text-sidebar-foreground placeholder:text-sidebar-foreground/40 focus:outline-none focus:ring-1 focus:ring-sidebar-ring"
        />
      </div>

      {/* Count */}
      <div className="px-2">
        <span className="text-[10px] text-sidebar-foreground/40">
          {search && filtered.length !== tables.length
            ? `${filtered.length} / ${tables.length} tables`
            : `${tables.length} tables`}
        </span>
      </div>

      {/* Table list */}
      <div className="max-h-[300px] overflow-y-auto px-1">
        {filtered.length === 0 ? (
          <p className="px-2 py-2 text-xs text-sidebar-foreground/40 text-center">
            No tables match
          </p>
        ) : (
          groups.map((group) => (
            <div key={group.prefix || "__root"}>
              {group.prefix && groups.length > 1 && (
                <button
                  onClick={() => toggleGroup(group.prefix)}
                  className="flex items-center gap-1 w-full px-1 py-1 text-[10px] font-semibold text-sidebar-foreground/60 uppercase tracking-wider hover:text-sidebar-foreground transition-colors"
                >
                  <ChevronRight
                    className={cn(
                      "h-2.5 w-2.5 transition-transform",
                      !collapsedGroups.has(group.prefix) && "rotate-90"
                    )}
                  />
                  {group.prefix}
                  <span className="font-normal">({group.tables.length})</span>
                </button>
              )}

              {!collapsedGroups.has(group.prefix) &&
                group.tables.map((table) => (
                  <SchemaTableRow
                    key={table.name}
                    table={table}
                    isExpanded={expandedTables.has(table.name)}
                    onToggle={() => toggleTable(table.name)}
                    onTableClick={onTableClick}
                  />
                ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function SchemaTableRow({
  table,
  isExpanded,
  onToggle,
  onTableClick,
}: {
  table: SchemaTable;
  isExpanded: boolean;
  onToggle: () => void;
  onTableClick?: (name: string) => void;
}) {
  const displayName = table.name.includes(".")
    ? table.name.slice(table.name.indexOf(".") + 1)
    : table.name;

  return (
    <div>
      <div className="flex items-center gap-0.5 group">
        <button
          onClick={onToggle}
          className="flex items-center gap-1.5 flex-1 min-w-0 rounded-md px-1.5 py-1 text-xs text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors"
        >
          <ChevronRight
            className={cn(
              "h-3 w-3 shrink-0 text-sidebar-foreground/40 transition-transform",
              isExpanded && "rotate-90"
            )}
          />
          <Table2 className="h-3 w-3 shrink-0 text-sidebar-foreground/40" />
          {table.description ? (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="truncate font-mono text-[11px]">{displayName}</span>
                </TooltipTrigger>
                <TooltipContent side="right">
                  <p className="max-w-[200px]">{table.description}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          ) : (
            <span className="truncate font-mono text-[11px]">{displayName}</span>
          )}
        </button>
        {onTableClick && (
          <button
            onClick={() => onTableClick(table.name)}
            className="opacity-0 group-hover:opacity-100 shrink-0 rounded p-0.5 text-sidebar-foreground/40 hover:text-sidebar-foreground transition-all"
            title={`Ask about ${table.name}`}
          >
            <Search className="h-3 w-3" />
          </button>
        )}
      </div>

      {isExpanded && (
        <div className="ml-7 mb-1 space-y-px">
          {table.columns.map((col) => (
            <div
              key={col.name}
              className="flex items-center gap-1.5 px-1.5 py-0.5 text-[11px] text-sidebar-foreground/60"
            >
              <Columns3 className="h-2.5 w-2.5 shrink-0" />
              <span className="font-mono truncate">{col.name}</span>
              <span className="ml-auto text-[10px] text-sidebar-foreground/35 shrink-0">
                {col.type}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
