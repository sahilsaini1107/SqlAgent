import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StreamHandlers } from "../lib/api";
import type { ChatResponse } from "../types";

// --- Mocks -----------------------------------------------------------------

const postChatStream = vi.fn();

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    postChatStream: (...args: unknown[]) => postChatStream(...args),
    deleteServerConversation: vi.fn(),
  };
});

let counter = 0;
vi.mock("../lib/storage", () => ({
  loadConversations: () => [],
  saveConversations: vi.fn(),
  uid: () => `id-${++counter}`,
}));

import { useConversations } from "./useConversations";

function chatResponse(overrides: Partial<ChatResponse> = {}): ChatResponse {
  return {
    conversation_id: "server-1",
    trace_id: "trace-1",
    intent: null,
    status: "ok",
    sql: "SELECT 1",
    explanation: "Here you go.",
    assumptions: [],
    clarification: null,
    refusal: null,
    validation: { passed: true, issues: [], warnings: [] },
    result: null,
    dialect: "sqlite",
    plan: null,
    usage: null,
    ...overrides,
  };
}

beforeEach(() => {
  counter = 0;
  postChatStream.mockReset();
  localStorage.clear();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useConversations", () => {
  it("happy path: creates a conversation, adds user + assistant turns", async () => {
    postChatStream.mockImplementation(
      async (
        _message: string,
        _serverId: string | null,
        _execute: boolean,
        _dialect: string,
        handlers: StreamHandlers,
      ) => {
        handlers.onStart?.("server-1");
        handlers.onStage?.("planning");
        handlers.onResult(chatResponse());
      },
    );

    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.send("show me users", true, {});
    });

    await waitFor(() => expect(result.current.active).not.toBeNull());

    const turns = result.current.active?.turns ?? [];
    expect(turns).toHaveLength(2);
    expect(turns[0]).toMatchObject({ role: "user", text: "show me users" });
    expect(turns[1].role).toBe("assistant");
    expect(result.current.active?.serverId).toBe("server-1");
    expect(result.current.freshTurnId).toBe(turns[1].id);
    expect(result.current.pending).toBeNull();
  });

  it("stream error: records an error turn and clears pending", async () => {
    postChatStream.mockRejectedValue(new Error("stream blew up"));

    const { result } = renderHook(() => useConversations());

    await act(async () => {
      await result.current.send("break it", true, {});
    });

    await waitFor(() => expect(result.current.pending).toBeNull());

    const turns = result.current.active?.turns ?? [];
    expect(turns).toHaveLength(2);
    expect(turns[0].role).toBe("user");
    expect(turns[1]).toMatchObject({ role: "error", stopped: false });
    expect((turns[1] as { text: string }).text).toContain("stream blew up");
  });
});
