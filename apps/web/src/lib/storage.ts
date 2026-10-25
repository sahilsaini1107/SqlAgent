import type { Conversation } from "../types";

const KEY = "sql-agent.conversations.v1";
const MAX_CONVERSATIONS = 60;
// Results are capped server-side, but keep stored history small so localStorage never fills up.
const MAX_STORED_ROWS = 200;

export function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Conversation[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function compact(conversation: Conversation): Conversation {
  return {
    ...conversation,
    turns: conversation.turns.map((turn) => {
      if (turn.role !== "assistant" || !turn.response.result) return turn;
      const result = turn.response.result;
      if (result.rows.length <= MAX_STORED_ROWS) return turn;
      return {
        ...turn,
        response: {
          ...turn.response,
          result: { ...result, rows: result.rows.slice(0, MAX_STORED_ROWS), truncated: true },
        },
      };
    }),
  };
}

export function saveConversations(conversations: Conversation[]): void {
  try {
    const kept = conversations
      .filter((c) => c.turns.length > 0)
      .slice(0, MAX_CONVERSATIONS)
      .map(compact);
    localStorage.setItem(KEY, JSON.stringify(kept));
  } catch {
    // storage full or unavailable — history just won't persist this session
  }
}

export function uid(): string {
  return crypto.randomUUID();
}
