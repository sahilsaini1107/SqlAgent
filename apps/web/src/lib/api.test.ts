import { describe, expect, it, vi } from "vitest";

import { handleSseBlock, type StreamHandlers } from "./api";
import type { ChatResponse } from "../types";

function makeHandlers() {
  const onStart = vi.fn();
  const onStage = vi.fn();
  const onResult = vi.fn();
  const handlers: StreamHandlers = { onStart, onStage, onResult };
  return { handlers, onStart, onStage, onResult };
}

describe("handleSseBlock", () => {
  it("parses a start frame", () => {
    const { handlers, onStart } = makeHandlers();
    handleSseBlock('event: start\ndata: {"conversation_id":"abc"}', handlers);
    expect(onStart).toHaveBeenCalledWith("abc");
  });

  it("parses a stage frame", () => {
    const { handlers, onStage } = makeHandlers();
    handleSseBlock('event: stage\ndata: {"status":"planning"}', handlers);
    expect(onStage).toHaveBeenCalledWith("planning");
  });

  it("parses a result frame as the ChatResponse payload", () => {
    const { handlers, onResult } = makeHandlers();
    const payload = { conversation_id: "abc", status: "ok", sql: "SELECT 1" };
    handleSseBlock(`event: result\ndata: ${JSON.stringify(payload)}`, handlers);
    expect(onResult).toHaveBeenCalledTimes(1);
    const arg = onResult.mock.calls[0][0] as ChatResponse;
    expect(arg.conversation_id).toBe("abc");
    expect(arg.sql).toBe("SELECT 1");
  });

  it("skips a malformed frame without throwing", () => {
    const { handlers, onResult } = makeHandlers();
    expect(() => handleSseBlock("event: result\ndata: {not json", handlers)).not.toThrow();
    expect(onResult).not.toHaveBeenCalled();
  });

  it("ignores SSE comment / keepalive lines", () => {
    const { handlers, onStart, onStage, onResult } = makeHandlers();
    handleSseBlock(": keepalive", handlers);
    expect(onStart).not.toHaveBeenCalled();
    expect(onStage).not.toHaveBeenCalled();
    expect(onResult).not.toHaveBeenCalled();
  });

  it("ignores a comment line mixed into an otherwise valid frame", () => {
    const { handlers, onStage } = makeHandlers();
    handleSseBlock(': ping\nevent: stage\ndata: {"status":"validating"}', handlers);
    expect(onStage).toHaveBeenCalledWith("validating");
  });

  it("does nothing for a data-less block", () => {
    const { handlers, onStart, onStage, onResult } = makeHandlers();
    handleSseBlock("event: stage", handlers);
    expect(onStart).not.toHaveBeenCalled();
    expect(onStage).not.toHaveBeenCalled();
    expect(onResult).not.toHaveBeenCalled();
  });
});
