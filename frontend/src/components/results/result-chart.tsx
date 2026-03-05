"use client";

import { useMemo, useState } from "react";
import { motion } from "motion/react";
import { BarChart3, Table2 } from "lucide-react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  type PieLabelRenderProps,
} from "recharts";

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

type ChartType = "bar" | "pie" | null;

interface ColumnAnalysis {
  stringColumns: string[];
  numericColumns: string[];
}

function analyzeColumns(data: Record<string, unknown>[]): ColumnAnalysis {
  if (data.length === 0) return { stringColumns: [], numericColumns: [] };

  const keys = Object.keys(data[0]);
  const stringColumns: string[] = [];
  const numericColumns: string[] = [];

  for (const key of keys) {
    const nonNullValues = data
      .map((row) => row[key])
      .filter((v) => v != null);
    if (nonNullValues.length === 0) continue;

    const allNumeric = nonNullValues.every(
      (v) => typeof v === "number" || (typeof v === "string" && !isNaN(Number(v)) && v.trim() !== "")
    );

    if (allNumeric) {
      numericColumns.push(key);
    } else {
      stringColumns.push(key);
    }
  }

  return { stringColumns, numericColumns };
}

function detectChartType(
  data: Record<string, unknown>[],
  analysis: ColumnAnalysis
): ChartType {
  const { stringColumns, numericColumns } = analysis;

  if (data.length > 50 || data.length === 0) return null;
  if (stringColumns.length !== 1) return null;
  if (numericColumns.length < 1 || numericColumns.length > 3) return null;

  if (numericColumns.length === 1 && data.length <= 8) return "pie";
  return "bar";
}

interface ResultChartProps {
  data: Record<string, unknown>[];
}

export function ResultChart({ data }: ResultChartProps) {
  const [showChart, setShowChart] = useState(true);

  const analysis = useMemo(() => analyzeColumns(data), [data]);
  const chartType = useMemo(() => detectChartType(data, analysis), [data, analysis]);

  if (!chartType) return null;

  // Normalize numeric values for charting
  const chartData = useMemo(
    () =>
      data.map((row) => {
        const normalized: Record<string, unknown> = { ...row };
        for (const col of analysis.numericColumns) {
          normalized[col] = Number(row[col]);
        }
        return normalized;
      }),
    [data, analysis.numericColumns]
  );

  const labelKey = analysis.stringColumns[0];
  const valueKeys = analysis.numericColumns;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex justify-end mb-1">
        <button
          onClick={() => setShowChart((s) => !s)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          title={showChart ? "Hide chart" : "Show chart"}
        >
          {showChart ? (
            <Table2 className="h-3.5 w-3.5" />
          ) : (
            <BarChart3 className="h-3.5 w-3.5" />
          )}
          {showChart ? "Table only" : "Show chart"}
        </button>
      </div>

      {showChart && (
        <div className="h-[260px] w-full rounded-md border border-transparent transition-colors hover:border-foreground/10 p-1">
          <ResponsiveContainer width="100%" height="100%">
            {chartType === "pie" ? (
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey={valueKeys[0]}
                  nameKey={labelKey}
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label={(props: PieLabelRenderProps) =>
                    `${props.name ?? ""} ${(((props.percent as number) ?? 0) * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {chartData.map((_, idx) => (
                    <Cell
                      key={idx}
                      fill={CHART_COLORS[idx % CHART_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            ) : (
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey={labelKey}
                  tick={{ fontSize: 11 }}
                  interval={0}
                  angle={chartData.length > 6 ? -30 : 0}
                  textAnchor={chartData.length > 6 ? "end" : "middle"}
                  height={chartData.length > 6 ? 60 : 30}
                />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                {valueKeys.length > 1 && <Legend />}
                {valueKeys.map((key, idx) => (
                  <Bar
                    key={key}
                    dataKey={key}
                    fill={CHART_COLORS[idx % CHART_COLORS.length]}
                    radius={[4, 4, 0, 0]}
                  />
                ))}
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </motion.div>
  );
}
