// Backend model mirrors

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "executed"
  | "failed";

export interface QueryResponse {
  query_id: string;
  question: string;
  generated_sql: string;
  validation_errors: string[];
  approval_status: ApprovalStatus;
  message: string;
  result: Record<string, unknown>[] | null;
  answer: string | null;
  error: string | null;
  query_type: "simple" | "analytical";
  analysis_plan: Record<string, string>[] | null;
  analysis_steps: Record<string, unknown>[] | null;
}

export interface ApprovalResponse {
  query_id: string;
  approval_status: ApprovalStatus;
  result: Record<string, unknown>[] | null;
  answer: string | null;
  error: string | null;
}

export interface CreateSessionResponse {
  session_id: string;
}

export interface SessionHistoryResponse {
  session_id: string;
  queries: Record<string, unknown>[];
  total: number;
}

export interface HealthResponse {
  status: string;
  database: string;
  metrics?: Record<string, unknown>;
}

// Frontend types

export type SSEEventType =
  | "schema_discovery_started"
  | "schema_discovered"
  | "classifying_query"
  | "query_classified"
  | "llm_generation_started"
  | "sql_generated"
  | "answer_generated"
  | "validation_passed"
  | "validation_failed"
  | "query_execution_started"
  | "query_executed"
  | "query_execution_failed"
  | "self_correction_triggered"
  | "planning_analysis"
  | "analysis_plan_created"
  | "plan_step_started"
  | "plan_step_sql_generated"
  | "plan_step_executed"
  | "plan_step_failed"
  | "analysis_synthesis_started"
  | "analysis_complete"
  | "analysis_validation_warning"
  | "analysis_validation_passed"
  | "done";

export type StepStatus = "active" | "completed" | "error";

export interface PipelineStep {
  event: SSEEventType;
  label: string;
  status: StepStatus;
  detail?: string;
  data?: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  pipelineSteps?: PipelineStep[];
  queryResponse?: QueryResponse;
  isStreaming?: boolean;
  error?: string;
}

export interface Session {
  id: string;
  label: string;
  createdAt: Date;
}
