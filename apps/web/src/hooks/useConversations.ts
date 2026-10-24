import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, deleteServerConversation, postChatStream } from "../lib/api";
import { loadConversations, saveConversations, uid } from "../lib/storage";
import type { AssistantTurn, Conversation, Dialect, ErrorTurn, Turn, UserTurn } from "../types";

export interface SendOptions {
  /** Drop this user turn and everything after it before sending (edit / regenerate). */
  replaceFrom?: string;
  /** Start a new conversation regardless of which one is active. */
  fresh?: boolean;
  /** SQL dialect to render the answer in (default sqlite). */
  dialect?: Dialect;
}

export interface Pending {
  conversationId: string;
  stages: string[];
  startedAt: number;
}

function titleFrom(text: string): string {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > 48 ? `${clean.slice(0, 46)}…` : clean;
}

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  // Only answers that arrive in this session animate in; restored history renders instantly.
  const [freshTurnId, setFreshTurnId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const conversationsRef = useRef(conversations);
  conversationsRef.current = conversations;

  useEffect(() => {
    saveConversations(conversations);
  }, [conversations]);

  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? null,
    [conversations, activeId],
  );

  const patch = useCallback((id: string, fn: (c: Conversation) => Conversation) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? fn(c) : c)));
  }, []);

  const pushTurn = useCallback(
    (id: string, turn: Turn) =>
      patch(id, (c) => ({ ...c, turns: [...c.turns, turn], updatedAt: Date.now() })),
    [patch],
  );

  const send = useCallback(
    async (message: string, execute: boolean, options: SendOptions = {}) => {
      const text = message.trim();
      if (!text || pending) return;

      let conversation = options.fresh
        ? null
        : (conversationsRef.current.find((c) => c.id === activeId) ?? null);
      if (!conversation) {
        conversation = {
          id: uid(),
          serverId: null,
          title: titleFrom(text),
          pinned: false,
          turns: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        };
        const created = conversation;
        setConversations((prev) => [created, ...prev]);
        setActiveId(created.id);
      }
      const convId = conversation.id;

      if (options.replaceFrom) {
        const cut = conversation.turns.findIndex((t) => t.id === options.replaceFrom);
        if (cut >= 0) {
          patch(convId, (c) => ({
            ...c,
            turns: c.turns.slice(0, cut),
            title: cut === 0 ? titleFrom(text) : c.title,
          }));
        }
      }

      const userTurn: UserTurn = { id: uid(), role: "user", text, execute, at: Date.now() };
      pushTurn(convId, userTurn);

      const controller = new AbortController();
      abortRef.current = controller;
      const startedAt = performance.now();
      const stages: string[] = [];
      setPending({ conversationId: convId, stages: [], startedAt: Date.now() });

      const dialect = options.dialect ?? "sqlite";
      const run = async (serverId: string | null) =>
        postChatStream(
          text,
          serverId,
          execute,
          dialect,
          {
            onStart: (id) => patch(convId, (c) => ({ ...c, serverId: id })),
            onStage: (status) => {
              if (stages[stages.length - 1] === status) return;
              stages.push(status);
              setPending((p) => (p ? { ...p, stages: [...stages] } : p));
            },
            onResult: (response) => {
              const turn: AssistantTurn = {
                id: uid(),
                role: "assistant",
                response,
                stages: [...stages],
                elapsedMs: Math.round(performance.now() - startedAt),
                at: Date.now(),
              };
              setFreshTurnId(turn.id);
              patch(convId, (c) => ({
                ...c,
                serverId: response.conversation_id,
                turns: [...c.turns, turn],
                updatedAt: Date.now(),
              }));
            },
          },
          controller.signal,
        );

      try {
        try {
          await run(conversation.serverId);
        } catch (err) {
          // The server forgot this conversation (e.g. its store was reset): start a fresh one.
          if (err instanceof ApiError && err.status === 404 && conversation.serverId) {
            await run(null);
          } else {
            throw err;
          }
        }
      } catch (err) {
        const stopped = controller.signal.aborted;
        const errorTurn: ErrorTurn = {
          id: uid(),
          role: "error",
          text: stopped
            ? "Stopped before an answer came back."
            : err instanceof Error
              ? err.message
              : String(err),
          stopped,
          at: Date.now(),
        };
        pushTurn(convId, errorTurn);
      } finally {
        abortRef.current = null;
        setPending(null);
      }
    },
    [activeId, patch, pending, pushTurn],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const newChat = useCallback(() => setActiveId(null), []);

  const select = useCallback((id: string) => setActiveId(id), []);

  const remove = useCallback(
    (id: string) => {
      const target = conversationsRef.current.find((c) => c.id === id);
      if (target?.serverId) deleteServerConversation(target.serverId);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) setActiveId(null);
    },
    [activeId],
  );

  const rename = useCallback(
    (id: string, title: string) => {
      const clean = title.trim();
      if (clean) patch(id, (c) => ({ ...c, title: clean }));
    },
    [patch],
  );

  const togglePin = useCallback(
    (id: string) => patch(id, (c) => ({ ...c, pinned: !c.pinned })),
    [patch],
  );

  return {
    conversations,
    active,
    activeId,
    pending,
    freshTurnId,
    send,
    stop,
    newChat,
    select,
    remove,
    rename,
    togglePin,
  };
}
