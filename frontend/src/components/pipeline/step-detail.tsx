"use client";

import { useEffect, useMemo, useState } from "react";
import { Copy, Check, AlertCircle } from "lucide-react";
import { format as formatSQL } from "sql-formatter";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface StepDetailProps {
  sql: string | null;
  result: Record<string, unknown>[] | null;
  error: string | null;
}

const MAX_PREVIEW_ROWS = 5;

export function StepDetail({ sql, result, error }: StepDetailProps) {
  const [copied, setCopied] = useState(false);
  const [highlighted, setHighlighted] = useState("");

  const formattedSQL = useMemo(() => {
    if (!sql) return "";
    try {
      return formatSQL(sql, { language: "sql", tabWidth: 2, keywordCase: "upper" });
    } catch {
      return sql;
    }
  }, [sql]);

  useEffect(() => {
    if (!formattedSQL) return;
    let cancelled = false;
    import("@/lib/shiki").then(({ highlightSQL }) => {
      highlightSQL(formattedSQL).then((html) => {
        if (!cancelled) setHighlighted(html);
      });
    });
    return () => {
      cancelled = true;
    };
  }, [formattedSQL]);

  const handleCopy = async () => {
    if (!sql) return;
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const previewRows = result?.slice(0, MAX_PREVIEW_ROWS) ?? [];
  const columns = previewRows.length > 0 ? Object.keys(previewRows[0]) : [];
  const totalRows = result?.length ?? 0;

  // Shiki generates sanitized HTML from code strings (no user input in HTML) — safe to render.
  // This follows the same pattern as SQLAccordion (sql-accordion.tsx:82-85).
  return (
    <div className="mt-1.5 space-y-2">
      {/* SQL block */}
      {sql && (
        <div className="relative rounded-md border border-blue-200 bg-blue-50/50">
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-1 right-1 h-6 w-6 z-10"
            onClick={handleCopy}
          >
            {copied ? (
              <Check className="h-3 w-3 text-emerald-600" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </Button>
          {highlighted ? (
            <div
              className="overflow-x-auto rounded-md bg-white/80 p-2 text-xs [&_pre]:!bg-transparent [&_pre]:!m-0 [&_code]:!bg-transparent"
              dangerouslySetInnerHTML={{ __html: highlighted }}
            />
          ) : (
            <pre className="overflow-x-auto rounded-md bg-white/80 p-2 text-xs font-mono whitespace-pre-wrap">
              {formattedSQL}
            </pre>
          )}
        </div>
      )}

      {/* Result preview table */}
      {previewRows.length > 0 && (
        <div>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((col) => (
                    <TableHead key={col} className="text-xs h-7 whitespace-nowrap">
                      {col}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewRows.map((row, ri) => (
                  <TableRow key={ri}>
                    {columns.map((col) => (
                      <TableCell
                        key={col}
                        className="text-xs py-1 whitespace-nowrap"
                      >
                        {row[col] === null || row[col] === undefined ? (
                          <span className="text-muted-foreground italic">null</span>
                        ) : (
                          String(row[col])
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {totalRows > MAX_PREVIEW_ROWS && (
            <p className="text-[10px] text-muted-foreground mt-1">
              Showing {MAX_PREVIEW_ROWS} of {totalRows} rows
            </p>
          )}
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="flex items-start gap-1.5 text-xs text-red-600">
          <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <p>{error}</p>
        </div>
      )}
    </div>
  );
}
