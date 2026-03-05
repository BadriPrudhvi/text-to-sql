"use client";

import { useMemo } from "react";
import { motion } from "motion/react";
import { FileDown } from "lucide-react";
import { AnswerCard } from "@/components/results/answer-card";
import { ResultChart } from "@/components/results/result-chart";
import { exportMarkdown } from "@/lib/export";
import type { QueryResponse } from "@/lib/types";

interface KPI {
  label: string;
  value: string;
}

function extractKPIs(analysisSteps: Record<string, unknown>[]): KPI[] {
  const kpis: KPI[] = [];

  for (const step of analysisSteps) {
    const result = step.result as Record<string, unknown>[] | null;
    if (!result || result.length === 0) continue;

    // Single-row results with numeric values make good KPIs
    if (result.length === 1) {
      const row = result[0];
      for (const [key, val] of Object.entries(row)) {
        if (typeof val === "number") {
          const numVal = val;
          kpis.push({
            label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
            value: formatKPIValue(numVal),
          });
        }
      }
    }
    if (kpis.length >= 4) break;
  }

  return kpis.slice(0, 4);
}

function formatKPIValue(val: number): string {
  if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (Math.abs(val) >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
  if (Number.isInteger(val)) return val.toLocaleString();
  return val.toFixed(2);
}

interface ChartableStep {
  description: string;
  data: Record<string, unknown>[];
}

function extractChartableSteps(analysisSteps: Record<string, unknown>[]): ChartableStep[] {
  const chartable: ChartableStep[] = [];

  for (const step of analysisSteps) {
    const result = step.result as Record<string, unknown>[] | null;
    const description = (step.description as string) || "";
    if (!result || result.length <= 1) continue;

    const keys = Object.keys(result[0]);
    const hasString = keys.some((k) =>
      result.some((r) => r[k] != null && typeof r[k] === "string" && isNaN(Number(r[k] as string)))
    );
    const hasNumeric = keys.some((k) =>
      result.some((r) => r[k] != null && !isNaN(Number(r[k]))) &&
      result.every((r) => r[k] == null || !isNaN(Number(r[k])))
    );

    if (hasString && hasNumeric && result.length <= 50) {
      chartable.push({ description, data: result });
    }
  }

  return chartable.slice(0, 3);
}

interface ReportCardProps {
  queryResponse: QueryResponse;
  question: string;
}

export function ReportCard({ queryResponse, question }: ReportCardProps) {
  const { answer, analysis_steps } = queryResponse;
  const steps = useMemo(() => analysis_steps ?? [], [analysis_steps]);

  const kpis = useMemo(() => extractKPIs(steps), [steps]);
  const chartableSteps = useMemo(() => extractChartableSteps(steps), [steps]);

  const handleExport = () => {
    if (answer) {
      const header = `# ${question}\n\n`;
      exportMarkdown(header + answer);
    }
  };

  return (
    <motion.div
      className="space-y-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {/* Report header */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold leading-snug line-clamp-2">
          {question}
        </h3>
        {answer && (
          <button
            onClick={handleExport}
            className="flex items-center gap-1 shrink-0 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title="Download report as Markdown"
          >
            <FileDown className="h-3.5 w-3.5" />
            Export
          </button>
        )}
      </div>

      {/* KPI cards */}
      {kpis.length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {kpis.map((kpi, i) => (
            <motion.div
              key={i}
              className="rounded-lg border bg-card p-3"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: i * 0.05 }}
            >
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide truncate">
                {kpi.label}
              </p>
              <p className="text-lg font-bold mt-0.5">{kpi.value}</p>
            </motion.div>
          ))}
        </div>
      )}

      {/* Per-step mini charts */}
      {chartableSteps.map((step, i) => (
        <div key={i} className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">
            {step.description}
          </p>
          <ResultChart data={step.data} />
        </div>
      ))}

      {/* Narrative answer */}
      {answer && <AnswerCard answer={answer} />}
    </motion.div>
  );
}
