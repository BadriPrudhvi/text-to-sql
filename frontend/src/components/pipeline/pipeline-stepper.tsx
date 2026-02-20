"use client";

import { useState } from "react";
import {
  Search,
  Brain,
  Code,
  Check,
  Play,
  AlertTriangle,
  List,
  Zap,
  FileText,
  Sparkles,
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle2,
  CircleAlert,
} from "lucide-react";
import type { PipelineStep, StepStatus } from "@/lib/types";
import { EVENT_META } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { QueryTypeBadge } from "@/components/ui/query-type-badge";
import { StepDetail } from "@/components/pipeline/step-detail";

const ICON_MAP = {
  search: Search,
  brain: Brain,
  code: Code,
  check: Check,
  play: Play,
  alert: AlertTriangle,
  list: List,
  zap: Zap,
  "file-text": FileText,
  sparkles: Sparkles,
} as const;

function StepIcon({ icon, status }: { icon: keyof typeof ICON_MAP; status: StepStatus }) {
  if (status === "active") {
    return <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />;
  }
  const Icon = ICON_MAP[icon];
  return (
    <Icon
      className={cn(
        "h-3.5 w-3.5",
        status === "completed" && "text-emerald-500",
        status === "error" && "text-red-500"
      )}
    />
  );
}

interface PipelineStepperProps {
  steps: PipelineStep[];
  isStreaming: boolean;
  analysisSteps?: Record<string, unknown>[] | null;
}

export function PipelineStepper({ steps, isStreaming, analysisSteps }: PipelineStepperProps) {
  const [expanded, setExpanded] = useState(false);
  const [expandedStepIndices, setExpandedStepIndices] = useState<Set<number>>(new Set());

  const toggleStepDetail = (stepIndex: number) => {
    setExpandedStepIndices((prev) => {
      const next = new Set(prev);
      if (next.has(stepIndex)) next.delete(stepIndex);
      else next.add(stepIndex);
      return next;
    });
  };

  const visibleSteps = steps.filter((s) => EVENT_META[s.event]?.visible);

  if (visibleSteps.length === 0 && !isStreaming) return null;

  const completedCount = visibleSteps.filter((s) => s.status === "completed").length;
  const hasError = visibleSteps.some((s) => s.status === "error");
  const activeStep = visibleSteps.find((s) => s.status === "active");
  const isDone = !isStreaming;
  const total = visibleSteps.length;

  // Extract query type from the classification step (hidden but carries data)
  const classifiedStep = steps.find((s) => s.event === "query_classified");
  const queryType = (classifiedStep?.data?.query_type as string) || null;

  return (
    <div className="mb-3">
      {/* Header row: summary bar + query type badge */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className={cn(
            "flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs transition-colors",
            isDone
              ? hasError
                ? "bg-red-50 text-red-700 hover:bg-red-100"
                : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
              : "bg-blue-50 text-blue-700 hover:bg-blue-100"
          )}
        >
          {/* Status icon */}
          {isStreaming ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
          ) : hasError ? (
            <CircleAlert className="h-3.5 w-3.5 shrink-0" />
          ) : (
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
          )}

          {/* Label */}
          <span className="font-medium">
            {isStreaming
              ? activeStep?.label || "Processing..."
              : hasError
              ? "Completed with issues"
              : "Completed"}
          </span>

          {/* Progress counter */}
          {total > 0 && (
            <span className="opacity-60">
              {isDone ? `${total} steps` : `${completedCount}/${total}`}
            </span>
          )}

          {/* Expand chevron */}
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 shrink-0 transition-transform duration-200",
              !expanded && "-rotate-90"
            )}
          />
        </button>

        {/* Query type badge — sits outside the button */}
        {queryType && <QueryTypeBadge queryType={queryType} />}
      </div>

      {/* Expanded step list */}
      {expanded && visibleSteps.length > 0 && (
        <div className="mt-1.5 ml-2.5">
          {visibleSteps.map((step, i) => {
            const meta = EVENT_META[step.event];
            const isLast = i === visibleSteps.length - 1;

            // Extract plan steps for the analysis_plan_created event
            const planSteps =
              step.event === "analysis_plan_created"
                ? (step.data?.steps as string[]) || []
                : [];

            // Check if this is an expandable analysis step
            const isAnalysisStep =
              step.event === "plan_step_executed" || step.event === "plan_step_failed";
            const stepIndex = isAnalysisStep
              ? (step.data?.step_index as number | undefined) ?? -1
              : -1;
            const stepData =
              isAnalysisStep && stepIndex >= 0 && analysisSteps
                ? analysisSteps[stepIndex]
                : null;
            const isStepExpanded = stepData && expandedStepIndices.has(stepIndex);

            return (
              <div key={i} className="flex gap-2.5">
                {/* Timeline rail */}
                <div className="flex flex-col items-center">
                  <div
                    className={cn(
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
                      step.status === "active" && "bg-blue-100",
                      step.status === "completed" && "bg-emerald-100",
                      step.status === "error" && "bg-red-100"
                    )}
                  >
                    <StepIcon icon={meta?.icon || "check"} status={step.status} />
                  </div>
                  {!isLast && (
                    <div
                      className={cn(
                        "w-px flex-1 min-h-3",
                        step.status === "completed"
                          ? "bg-emerald-200"
                          : step.status === "error"
                          ? "bg-red-200"
                          : "bg-border"
                      )}
                    />
                  )}
                </div>

                {/* Content */}
                <div className={cn("pb-3 min-w-0", isLast && "pb-1")}>
                  {stepData ? (
                    <button
                      onClick={() => toggleStepDetail(stepIndex)}
                      className="flex items-center gap-1 text-xs font-medium leading-5 hover:text-blue-600 transition-colors"
                    >
                      <ChevronRight
                        className={cn(
                          "h-3 w-3 shrink-0 transition-transform duration-200",
                          isStepExpanded && "rotate-90"
                        )}
                      />
                      {step.label}
                    </button>
                  ) : (
                    <p className="text-xs font-medium leading-5">{step.label}</p>
                  )}
                  {step.detail && !isStepExpanded && (
                    <p className="truncate text-xs text-muted-foreground mt-0.5">
                      {step.detail}
                    </p>
                  )}
                  {/* Expanded step detail */}
                  {isStepExpanded && stepData && (
                    <StepDetail
                      sql={(stepData.sql as string) || null}
                      result={(stepData.result as Record<string, unknown>[]) || null}
                      error={(stepData.error as string) || null}
                    />
                  )}
                  {/* Analysis plan sub-steps */}
                  {planSteps.length > 0 && (
                    <ol className="mt-1.5 space-y-0.5">
                      {planSteps.map((desc, j) => (
                        <li
                          key={j}
                          className="flex items-baseline gap-1.5 text-xs text-muted-foreground"
                        >
                          <span className="shrink-0 text-[10px] font-medium text-muted-foreground/60">
                            {j + 1}.
                          </span>
                          <span>{desc}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
