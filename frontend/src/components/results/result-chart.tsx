"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { BarChart3, ChevronLeft, ChevronRight, PieChartIcon, Table2, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
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

const MAX_LABEL_LENGTH = 20;

function truncateLabel(label: string, max = MAX_LABEL_LENGTH): string {
  if (label.length <= max) return label;
  return label.slice(0, max - 1) + "…";
}

type ChartType = "bar" | "pie" | "line";

interface ColumnAnalysis {
  stringColumns: string[];
  numericColumns: string[];
}

const ID_PATTERNS = /(?:^id$|_id$|Id$|ID$|_pk$|_fk$|_key$)/;

function looksLikeId(key: string, values: unknown[]): boolean {
  if (ID_PATTERNS.test(key)) return true;
  // All unique integers suggest a primary key / foreign key
  if (values.length >= 2 && values.every((v) => Number.isInteger(Number(v)))) {
    const unique = new Set(values.map(String));
    if (unique.size === values.length) return true;
  }
  return false;
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
      // Skip ID/key columns — they're not meaningful metrics
      if (looksLikeId(key, nonNullValues)) {
        stringColumns.push(key);
      } else {
        numericColumns.push(key);
      }
    } else {
      stringColumns.push(key);
    }
  }

  return { stringColumns, numericColumns };
}

const DATE_PATTERNS = [
  /^\d{4}-\d{2}-\d{2}/,
  /^\d{1,2}\/\d{1,2}\/\d{2,4}/,
  /^\d{4}\/\d{2}\/\d{2}/,
];

function isDateLike(value: unknown): boolean {
  if (value == null) return false;
  const str = String(value).trim();
  return DATE_PATTERNS.some((p) => p.test(str));
}

function hasDateColumn(data: Record<string, unknown>[], stringColumns: string[]): string | null {
  for (const col of stringColumns) {
    const nonNull = data.filter((r) => r[col] != null).slice(0, 5);
    if (nonNull.length > 0 && nonNull.every((r) => isDateLike(r[col]))) {
      return col;
    }
  }
  return null;
}

function detectChartType(
  data: Record<string, unknown>[],
  analysis: ColumnAnalysis
): ChartType | null {
  const { stringColumns, numericColumns } = analysis;

  if (data.length > 50 || data.length === 0) return null;
  if (stringColumns.length !== 1) return null;
  if (numericColumns.length < 1 || numericColumns.length > 3) return null;

  if (hasDateColumn(data, stringColumns)) return "line";
  if (numericColumns.length === 1 && data.length <= 8) return "pie";
  return "bar";
}

function isPieViable(analysis: ColumnAnalysis, dataLength: number): boolean {
  return analysis.numericColumns.length === 1 && dataLength <= 8;
}

function isLineViable(analysis: ColumnAnalysis, dataLength: number, data?: Record<string, unknown>[]): boolean {
  if (analysis.numericColumns.length < 1 || dataLength < 2) return false;
  if (!data) return false;
  // Line charts only make sense for ordered data (dates or large sequential datasets)
  return hasDateColumn(data, analysis.stringColumns) !== null || dataLength > 6;
}

// Custom tooltip for both chart types
function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="font-medium text-popover-foreground mb-1">{label ?? payload[0]?.name}</p>
      {payload.map((entry, idx) => (
        <div key={idx} className="flex items-center gap-2 text-muted-foreground">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span>{entry.name}:</span>
          <span className="font-medium text-popover-foreground">
            {typeof entry.value === "number" ? entry.value.toLocaleString() : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// Custom pie label that shows only percentage inside the slice
function PieLabel(props: PieLabelRenderProps) {
  const { cx, cy, midAngle, innerRadius, outerRadius, percent } = props;
  if (
    typeof cx !== "number" ||
    typeof cy !== "number" ||
    typeof midAngle !== "number" ||
    typeof innerRadius !== "number" ||
    typeof outerRadius !== "number" ||
    typeof percent !== "number"
  )
    return null;

  if (percent < 0.05) return null;

  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      className="text-[11px] font-medium pointer-events-none"
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

// Custom legend with truncated labels
function CompactLegend({ payload }: {
  payload?: Array<{ value: string; color: string }>;
}) {
  if (!payload?.length) return null;

  return (
    <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 mt-2 px-2">
      {payload.map((entry, idx) => (
        <div key={idx} className="flex items-center gap-1.5 text-[11px] text-muted-foreground" title={entry.value}>
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm shrink-0"
            style={{ backgroundColor: entry.color }}
          />
          <span className="truncate max-w-[140px]">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

interface ResultChartProps {
  data: Record<string, unknown>[];
}

export function ResultChart({ data }: ResultChartProps) {
  const analysis = useMemo(() => analyzeColumns(data), [data]);
  const defaultType = useMemo(() => detectChartType(data, analysis), [data, analysis]);
  const pieViable = useMemo(() => isPieViable(analysis, data.length), [analysis, data.length]);
  const lineViable = useMemo(() => isLineViable(analysis, data.length, data), [analysis, data]);

  const [chartType, setChartType] = useState<ChartType | "hidden">(defaultType ?? "hidden");
  const [tablePage, setTablePage] = useState(0);
  const TABLE_PAGE_SIZE = 10;

  // Sync default when data changes
  useEffect(() => {
    setChartType(defaultType ?? "hidden");
    setTablePage(0);
  }, [defaultType]);

  if (!defaultType) return null;

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

  const showChart = chartType !== "hidden";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex justify-end gap-1 mb-1">
        {showChart && (
          <div className="flex items-center gap-0.5 rounded-md border bg-muted/30 p-0.5">
            <button
              onClick={() => setChartType("bar")}
              className={cn(
                "rounded p-1 transition-colors",
                chartType === "bar"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
              title="Bar chart"
            >
              <BarChart3 className="h-3.5 w-3.5" />
            </button>
            {lineViable && (
              <button
                onClick={() => setChartType("line")}
                className={cn(
                  "rounded p-1 transition-colors",
                  chartType === "line"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
                title="Line chart"
              >
                <TrendingUp className="h-3.5 w-3.5" />
              </button>
            )}
            {pieViable && (
              <button
                onClick={() => setChartType("pie")}
                className={cn(
                  "rounded p-1 transition-colors",
                  chartType === "pie"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
                title="Pie chart"
              >
                <PieChartIcon className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        )}
        <button
          onClick={() => setChartType(showChart ? "hidden" : (defaultType ?? "bar"))}
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

      {!showChart && (() => {
        const totalPages = Math.ceil(chartData.length / TABLE_PAGE_SIZE);
        const pageRows = chartData.slice(tablePage * TABLE_PAGE_SIZE, (tablePage + 1) * TABLE_PAGE_SIZE);
        return (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-xs">
              <thead className="bg-muted/50 border-b">
                <tr>
                  {[labelKey, ...valueKeys].map((col) => (
                    <th key={col} className="px-3 py-2 text-left font-semibold text-muted-foreground whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {pageRows.map((row, i) => (
                  <tr key={i} className="hover:bg-muted/50 transition-colors">
                    {[labelKey, ...valueKeys].map((col) => (
                      <td key={col} className="px-3 py-1.5 whitespace-nowrap">
                        {typeof row[col] === "number" ? (row[col] as number).toLocaleString() : String(row[col] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-3 py-1.5 border-t">
                <p className="text-[10px] text-muted-foreground">
                  Page {tablePage + 1} of {totalPages}
                </p>
                <div className="flex gap-1">
                  <button
                    onClick={() => setTablePage((p) => p - 1)}
                    disabled={tablePage === 0}
                    className="rounded p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:pointer-events-none transition-colors"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => setTablePage((p) => p + 1)}
                    disabled={tablePage >= totalPages - 1}
                    className="rounded p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:pointer-events-none transition-colors"
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {showChart && (
        <div className="h-[280px] w-full rounded-md border border-transparent transition-colors hover:border-foreground/10 p-1">
          <ResponsiveContainer width="100%" height="100%">
            {chartType === "line" ? (
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey={labelKey}
                  tick={{ fontSize: 11 }}
                  interval={chartData.length > 15 ? Math.ceil(chartData.length / 10) - 1 : 0}
                  tickFormatter={(v: string) => truncateLabel(v, chartData.length > 15 ? 10 : 12)}
                  angle={chartData.length > 6 ? -45 : 0}
                  textAnchor={chartData.length > 6 ? "end" : "middle"}
                  height={chartData.length > 6 ? 80 : 35}
                />
                <YAxis tick={{ fontSize: 11 }} width={50} />
                <Tooltip content={<ChartTooltip />} />
                {valueKeys.length > 1 && <Legend content={<CompactLegend />} />}
                {valueKeys.map((key, idx) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 3, fill: CHART_COLORS[idx % CHART_COLORS.length] }}
                    activeDot={{ r: 5 }}
                  />
                ))}
              </LineChart>
            ) : chartType === "pie" ? (
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey={valueKeys[0]}
                  nameKey={labelKey}
                  cx="50%"
                  cy="45%"
                  outerRadius={85}
                  innerRadius={30}
                  label={PieLabel}
                  labelLine={false}
                  strokeWidth={2}
                  stroke="var(--background)"
                >
                  {chartData.map((_, idx) => (
                    <Cell
                      key={idx}
                      fill={CHART_COLORS[idx % CHART_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
                <Legend content={<CompactLegend />} />
              </PieChart>
            ) : (
              <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey={labelKey}
                  tick={{ fontSize: 11 }}
                  interval={chartData.length > 15 ? Math.ceil(chartData.length / 10) - 1 : 0}
                  tickFormatter={(v: string) => truncateLabel(v, chartData.length > 15 ? 10 : MAX_LABEL_LENGTH)}
                  angle={chartData.length > 4 ? -45 : 0}
                  textAnchor={chartData.length > 4 ? "end" : "middle"}
                  height={chartData.length > 4 ? 80 : 35}
                />
                <YAxis tick={{ fontSize: 11 }} width={50} />
                <Tooltip content={<ChartTooltip />} />
                {valueKeys.length > 1 && <Legend content={<CompactLegend />} />}
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
