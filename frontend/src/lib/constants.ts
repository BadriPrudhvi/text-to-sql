import type { SSEEventType } from "./types";

interface EventMeta {
  label: string;
  icon: "search" | "brain" | "code" | "check" | "play" | "alert" | "list" | "zap" | "file-text" | "sparkles";
  /** Show this step in the pipeline stepper UI */
  visible: boolean;
}

export const EVENT_META: Record<SSEEventType, EventMeta> = {
  // Internal — hidden from stepper
  schema_discovery_started: { label: "Discovering schema", icon: "search", visible: false },
  classifying_query: { label: "Classifying query", icon: "brain", visible: false },
  query_classified: { label: "Query classified", icon: "check", visible: false },
  llm_generation_started: { label: "Generating SQL", icon: "code", visible: false },
  validation_passed: { label: "Validation passed", icon: "check", visible: false },
  query_execution_started: { label: "Executing query", icon: "play", visible: false },
  planning_analysis: { label: "Planning analysis", icon: "list", visible: false },
  plan_step_sql_generated: { label: "Step SQL generated", icon: "code", visible: false },
  analysis_synthesis_started: { label: "Synthesizing results", icon: "sparkles", visible: false },
  analysis_validation_passed: { label: "Quality check passed", icon: "check", visible: false },
  done: { label: "Done", icon: "check", visible: false },

  // User-facing — shown in stepper
  schema_discovered: { label: "Loaded schema", icon: "search", visible: true },
  sql_generated: { label: "Generated SQL", icon: "code", visible: true },
  query_executed: { label: "Query executed", icon: "check", visible: true },
  answer_generated: { label: "Answer ready", icon: "sparkles", visible: true },
  validation_failed: { label: "Validation failed", icon: "alert", visible: true },
  query_execution_failed: { label: "Execution failed", icon: "alert", visible: true },
  self_correction_triggered: { label: "Self-correcting", icon: "zap", visible: true },
  analysis_plan_created: { label: "Analysis plan ready", icon: "list", visible: true },
  plan_step_started: { label: "Running analysis step", icon: "play", visible: true },
  plan_step_executed: { label: "Step completed", icon: "check", visible: true },
  plan_step_failed: { label: "Step failed", icon: "alert", visible: true },
  analysis_complete: { label: "Analysis complete", icon: "sparkles", visible: true },
  analysis_validation_warning: { label: "Quality check warning", icon: "alert", visible: true },
};
