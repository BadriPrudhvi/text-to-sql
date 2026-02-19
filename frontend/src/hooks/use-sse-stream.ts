"use client";

import { useCallback, useRef, useState } from "react";
import { streamQueryURL } from "@/lib/api";
import { EVENT_META } from "@/lib/constants";
import type {
  PipelineStep,
  QueryResponse,
  SSEEventType,
  StepStatus,
} from "@/lib/types";

interface SSEStreamState {
  pipelineSteps: PipelineStep[];
  finalResponse: QueryResponse | null;
  isStreaming: boolean;
  error: string | null;
}

function statusForEvent(event: SSEEventType): StepStatus {
  const errorEvents: SSEEventType[] = [
    "validation_failed",
    "query_execution_failed",
    "plan_step_failed",
    "analysis_validation_warning",
  ];
  if (errorEvents.includes(event)) return "error";

  const activeEvents: SSEEventType[] = [
    "schema_discovery_started",
    "classifying_query",
    "llm_generation_started",
    "query_execution_started",
    "planning_analysis",
    "plan_step_started",
    "plan_step_sql_generated",
    "analysis_synthesis_started",
  ];
  if (activeEvents.includes(event)) return "active";

  return "completed";
}

function detailForEvent(
  event: SSEEventType,
  data: Record<string, unknown>
): string | undefined {
  switch (event) {
    case "schema_discovered":
      return `${data.table_count} tables found`;
    case "query_classified":
      return `Type: ${data.query_type}`;
    case "sql_generated":
      return truncateSQL(data.sql as string);
    case "query_executed":
      return `${data.row_count} rows returned`;
    case "validation_failed":
      return (data.errors as string[])?.join(", ");
    case "query_execution_failed":
      return data.error as string;
    case "self_correction_triggered":
      return (data.warnings as string[])?.join(", ");
    case "analysis_plan_created":
      return `${data.step_count} steps planned`;
    case "plan_step_started":
      return data.description as string;
    case "plan_step_sql_generated":
      return truncateSQL(data.sql as string);
    case "plan_step_executed":
      return `${data.row_count} rows`;
    case "plan_step_failed":
      return data.error as string;
    case "analysis_complete":
      return "Insights ready";
    case "analysis_validation_warning":
      return (data.warnings as string[])?.join(", ");
    default:
      return undefined;
  }
}

function truncateSQL(sql: string | undefined): string | undefined {
  if (!sql) return undefined;
  const trimmed = sql.trim().replace(/\s+/g, " ");
  return trimmed.length > 80 ? trimmed.slice(0, 77) + "..." : trimmed;
}

export function useSSEStream() {
  const [state, setState] = useState<SSEStreamState>({
    pipelineSteps: [],
    finalResponse: null,
    isStreaming: false,
    error: null,
  });
  const eventSourceRef = useRef<EventSource | null>(null);

  const startStream = useCallback(
    (sessionId: string, question: string) => {
      // Close any existing stream
      eventSourceRef.current?.close();

      setState({
        pipelineSteps: [],
        finalResponse: null,
        isStreaming: true,
        error: null,
      });

      const url = streamQueryURL(sessionId, question);
      const es = new EventSource(url);
      eventSourceRef.current = es;

      // Accumulated state to build final response
      let sql = "";
      let answer = "";
      let result: Record<string, unknown>[] | null = null;
      let validationErrors: string[] = [];
      let queryId = "";
      let approvalStatus: string = "executed";
      let queryType: "simple" | "analytical" = "simple";
      let error: string | null = null;
      let analysisPlan: Record<string, string>[] | null = null;

      const allEventTypes: SSEEventType[] = Object.keys(
        EVENT_META
      ) as SSEEventType[];

      for (const eventType of allEventTypes) {
        es.addEventListener(eventType, (e: MessageEvent) => {
          if (eventType === "done") {
            es.close();
            eventSourceRef.current = null;

            // Parse done event — backend sends full record data
            let doneData: Record<string, unknown> = {};
            try {
              doneData = JSON.parse(e.data);
            } catch {
              // Fallback to accumulated values
            }

            const finalResp: QueryResponse = {
              query_id: (doneData.query_id as string) || queryId,
              question,
              generated_sql: (doneData.generated_sql as string) || sql,
              validation_errors:
                (doneData.validation_errors as string[]) || validationErrors,
              approval_status:
                ((doneData.approval_status as string) || approvalStatus) as QueryResponse["approval_status"],
              message: "",
              result:
                (doneData.result as Record<string, unknown>[] | null) ?? result,
              answer: (doneData.answer as string) || answer || null,
              error: (doneData.error as string) || error,
              query_type:
                ((doneData.query_type as string) || queryType) as "simple" | "analytical",
              analysis_plan:
                (doneData.analysis_plan as Record<string, string>[]) || analysisPlan,
              analysis_steps:
                (doneData.analysis_steps as Record<string, unknown>[]) || null,
            };

            setState((prev) => ({
              ...prev,
              // Mark any remaining active steps as completed
              pipelineSteps: prev.pipelineSteps.map((s) =>
                s.status === "active" ? { ...s, status: "completed" as StepStatus } : s
              ),
              finalResponse: finalResp,
              isStreaming: false,
            }));
            return;
          }

          let data: Record<string, unknown> = {};
          try {
            data = JSON.parse(e.data);
          } catch {
            // Some events may have empty or non-JSON data
          }

          // Accumulate response fields
          if (eventType === "sql_generated" || eventType === "plan_step_sql_generated") {
            sql = (data.sql as string) || sql;
          }
          if (eventType === "answer_generated" || eventType === "analysis_complete") {
            answer = (data.answer as string) || answer;
          }
          if (eventType === "query_executed" || eventType === "plan_step_executed") {
            result = (data.result as Record<string, unknown>[]) || result;
          }
          if (eventType === "validation_failed") {
            validationErrors = (data.errors as string[]) || [];
            approvalStatus = "pending";
          }
          if (eventType === "query_classified") {
            queryType = (data.query_type as "simple" | "analytical") || "simple";
          }
          if (eventType === "query_execution_failed") {
            error = (data.error as string) || null;
            approvalStatus = "failed";
          }
          if (data.query_id) {
            queryId = data.query_id as string;
          }
          if (eventType === "analysis_plan_created") {
            analysisPlan = (data.steps as Record<string, string>[]) || null;
          }

          const meta = EVENT_META[eventType];
          if (!meta) return;

          const step: PipelineStep = {
            event: eventType,
            label: meta.label,
            status: statusForEvent(eventType),
            detail: detailForEvent(eventType, data),
            data,
          };

          setState((prev) => {
            // Replace the last active step if this new step completes it
            const steps = [...prev.pipelineSteps];
            const lastIdx = steps.length - 1;
            if (
              lastIdx >= 0 &&
              steps[lastIdx].status === "active" &&
              step.status !== "active"
            ) {
              steps[lastIdx] = step;
            } else {
              steps.push(step);
            }
            return { ...prev, pipelineSteps: steps };
          });
        });
      }

      es.onerror = () => {
        es.close();
        eventSourceRef.current = null;
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          error: prev.error || "Connection lost. Please try again.",
        }));
      };
    },
    []
  );

  const stopStream = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setState((prev) => ({ ...prev, isStreaming: false }));
  }, []);

  return { ...state, startStream, stopStream };
}
