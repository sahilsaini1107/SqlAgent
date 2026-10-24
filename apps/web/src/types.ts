export interface ValidationIssue {
  code: string;
  message: string;
  severity: string;
}

export interface ValidationView {
  passed: boolean;
  issues: ValidationIssue[];
  warnings: ValidationIssue[];
}

export interface ResultView {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  duration_ms: number;
}

export interface ChatResponse {
  conversation_id: string;
  trace_id: string;
  intent: string | null;
  status: string;
  sql: string | null;
  explanation: string | null;
  assumptions: string[];
  clarification: string | null;
  refusal: string | null;
  validation: ValidationView;
  result: ResultView | null;
}

export interface SchemaColumn {
  name: string;
  type: string;
  nullable: boolean;
  primary_key: boolean;
}

export interface SchemaForeignKey {
  column: string;
  ref_table: string;
  ref_column: string;
}

export interface SchemaTable {
  name: string;
  columns: SchemaColumn[];
  foreign_keys: SchemaForeignKey[];
}

export interface SchemaView {
  dialect: string;
  tables: SchemaTable[];
}

export interface UserTurn {
  id: string;
  role: "user";
  text: string;
  execute: boolean;
  at: number;
}

export interface AssistantTurn {
  id: string;
  role: "assistant";
  response: ChatResponse;
  /** Pipeline stages streamed while this answer was produced, in order. */
  stages: string[];
  elapsedMs: number;
  at: number;
}

/** A request that never produced a response (network error, server error, or stopped). */
export interface ErrorTurn {
  id: string;
  role: "error";
  text: string;
  stopped: boolean;
  at: number;
}

export type Turn = UserTurn | AssistantTurn | ErrorTurn;

export interface Conversation {
  id: string;
  /** Server-side conversation id; null until the first request starts. */
  serverId: string | null;
  title: string;
  pinned: boolean;
  turns: Turn[];
  createdAt: number;
  updatedAt: number;
}
