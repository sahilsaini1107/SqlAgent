import type { ChatResponse, SchemaView } from "../types";

// Backend origin, baked in at build time (e.g. https://sql-agent-api.onrender.com). Empty in
// local dev, where the Vite proxy forwards same-origin /api and /health to the backend.
const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

function url(path: string): string {
  return `${API_BASE}${path}`;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function errorFrom(res: Response): Promise<ApiError> {
  let detail = `Request failed (${res.status})`;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // response had no JSON body
  }
  return new ApiError(detail, res.status);
}

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw await errorFrom(res);
  return (await res.json()) as T;
}

export async function fetchSchema(signal?: AbortSignal): Promise<SchemaView> {
  return parseJson<SchemaView>(await fetch(url("/api/schema"), { signal }));
}

export async function fetchHealth(signal?: AbortSignal): Promise<{ status: string; version: string }> {
  return parseJson(await fetch(url("/health"), { signal }));
}

export interface StreamHandlers {
  onStart?: (conversationId: string) => void;
  onStage?: (status: string) => void;
  onResult: (response: ChatResponse) => void;
}

export function handleSseBlock(block: string, handlers: StreamHandlers): void {
  let event = "";
  let data = "";
  for (const line of block.split("\n")) {
    // SSE comment / keepalive lines start with ':' and carry no event data.
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return;
  let payload: unknown;
  try {
    payload = JSON.parse(data);
  } catch {
    // A malformed or partial frame must not abort the whole stream — skip it.
    return;
  }
  const record = payload as Record<string, unknown>;
  if (event === "start") handlers.onStart?.(record.conversation_id as string);
  else if (event === "stage") handlers.onStage?.(record.status as string);
  else if (event === "result") handlers.onResult(payload as ChatResponse);
}

export async function postChatStream(
  message: string,
  conversationId: string | null,
  execute: boolean,
  dialect: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url("/api/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId, execute, dialect }),
    signal,
  });
  if (!res.ok || !res.body) throw await errorFrom(res);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) handleSseBlock(block, handlers);
  }
  if (buffer.trim()) handleSseBlock(buffer, handlers);
}

export function deleteServerConversation(conversationId: string): void {
  // Best-effort cleanup; local history is the source of truth for the UI.
  const path = `/api/conversations/${encodeURIComponent(conversationId)}`;
  fetch(url(path), { method: "DELETE" }).catch(() => undefined);
}
