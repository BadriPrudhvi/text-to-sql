"use client";

import { useEffect, useMemo, useState } from "react";
import { Copy, Check, Database } from "lucide-react";
import { format as formatSQL } from "sql-formatter";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";

interface SQLAccordionProps {
  sql: string;
}

export function SQLAccordion({ sql }: SQLAccordionProps) {
  const [copied, setCopied] = useState(false);
  const [highlighted, setHighlighted] = useState("");

  const formattedSQL = useMemo(() => {
    try {
      return formatSQL(sql, {
        language: "sql",
        tabWidth: 2,
        keywordCase: "upper",
      });
    } catch {
      return sql;
    }
  }, [sql]);

  useEffect(() => {
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
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!sql) return null;

  // shiki generates sanitized HTML from code (no user input in HTML generation) — safe to render
  return (
    <Accordion type="single" collapsible className="w-full">
      <AccordionItem value="sql" className="rounded-md border border-blue-200 bg-blue-50/50">
        <AccordionTrigger className="px-3 py-2 text-xs hover:no-underline">
          <div className="flex items-center gap-2">
            <Database className="h-3.5 w-3.5 text-blue-500" />
            <span className="font-medium text-blue-600">SQL Query</span>
          </div>
        </AccordionTrigger>
        <AccordionContent className="px-3 pb-3">
          <div className="relative">
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-1 right-1 h-7 w-7"
              onClick={handleCopy}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-emerald-600" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </Button>
            {highlighted ? (
              <div
                className="overflow-x-auto rounded bg-white/80 p-3 text-sm [&_pre]:!bg-transparent [&_pre]:!m-0 [&_code]:!bg-transparent"
                dangerouslySetInnerHTML={{ __html: highlighted }}
              />
            ) : (
              <pre className="overflow-x-auto rounded bg-white/80 p-3 text-sm font-mono whitespace-pre-wrap">
                {formattedSQL}
              </pre>
            )}
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
