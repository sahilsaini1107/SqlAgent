import { useEffect, useLayoutEffect, useRef, useState } from "react";

import type { Pending } from "../hooks/useConversations";
import { useCopy } from "../hooks/useToast";
import { useTypewriter } from "../hooks/useTypewriter";
import { chartSpec, followUps, headlineStats } from "../lib/insights";
import type { AssistantTurn, ChatResponse, Conversation, ErrorTurn, UserTurn } from "../types";
import { BarChart } from "./BarChart";
import {
  IconAlert,
  IconArrowUp,
  IconChart,
  IconCopy,
  IconExpand,
  IconInfo,
  IconPencil,
  IconRefresh,
  IconSparkles,
  IconTable,
  Logo,
} from "./Icons";
import type { InspectorTab } from "./Inspector";
import { PipelineLive, PipelineTrace } from "./Pipeline";
import { ResultsTable } from "./ResultsTable";
import { SqlBlock } from "./SqlBlock";
import { StatusBadge } from "./StatusBadge";

interface Props {
  conversation: Conversation;
  pending: Pending | null;
  freshTurnId: string | null;
  inspectedTurnId: string | null;
  onInspect: (turnId: string, tab?: InspectorTab) => void;
  onFollowUp: (prompt: string, execute?: boolean) => void;
  onResend: (turn: UserTurn) => void;
  onEdit: (turn: UserTurn) => void;
}

export function assistantText(response: ChatResponse): string {
  if (response.refusal) return response.refusal;
  if (response.clarification) return response.clarification;
  if (response.explanation) return response.explanation;
  if (response.status === "validation_failed") {
    return "I couldn't produce a query that passes validation. The issues are listed below — try rephrasing or narrowing the question.";
  }
  if (response.status === "execution_failed") {
    return "The query was valid but failed when it ran against the database.";
  }
  return "Done.";
}

export function ChatThread(props: Props) {
  const { conversation, pending } = props;
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [atBottom, setAtBottom] = useState(true);
  // Tracked in a ref so the ResizeObserver callback always sees the live value.
  const atBottomRef = useRef(true);
  const isPending = pending?.conversationId === conversation.id;

  const setPinned = (pinned: boolean) => {
    atBottomRef.current = pinned;
    setAtBottom(pinned);
  };

  const onScroll = () => {
    const el = scrollRef.current;
    if (el) setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 120);
  };

  const scrollToBottom = (smooth = true) =>
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: smooth ? "smooth" : "auto" });

  // Jump to the end when switching conversations; follow new content only if already at the bottom.
  useLayoutEffect(() => {
    scrollToBottom(false);
    setPinned(true);
  }, [conversation.id]);

  // Follow content growth (typewriter reveal, table/chart expansion) instead of discrete turn
  // counts, so the view stays pinned to the bottom — but only while the user hasn't scrolled away.
  useEffect(() => {
    const content = contentRef.current;
    if (!content || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (atBottomRef.current) scrollToBottom(false);
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, []);

  const turns = conversation.turns;
  const lastAssistantIndex = turns.map((t) => t.role).lastIndexOf("assistant");

  return (
    <div className="relative flex-1 overflow-hidden">
      <div ref={scrollRef} onScroll={onScroll} className="h-full overflow-y-auto">
        <div ref={contentRef} className="mx-auto flex max-w-3xl flex-col gap-6 px-4 pb-10 pt-6 sm:px-6">
          {turns.map((turn, index) => {
            if (turn.role === "user") {
              return <UserBubble key={turn.id} turn={turn} onEdit={() => props.onEdit(turn)} />;
            }
            const question = previousUser(turns, index);
            if (turn.role === "error") {
              return (
                <ErrorCard
                  key={turn.id}
                  turn={turn}
                  onRetry={question && !isPending ? () => props.onResend(question) : undefined}
                />
              );
            }
            return (
              <AssistantCard
                key={turn.id}
                turn={turn}
                question={question}
                fresh={turn.id === props.freshTurnId}
                inspected={turn.id === props.inspectedTurnId}
                isLast={index === lastAssistantIndex && index === turns.length - 1}
                busy={isPending}
                onInspect={(tab) => props.onInspect(turn.id, tab)}
                onFollowUp={props.onFollowUp}
                onRegenerate={question ? () => props.onResend(question) : undefined}
              />
            );
          })}
          {isPending && pending && (
            <div className="flex gap-3">
              <Logo size={28} />
              <PipelineLive stages={pending.stages} startedAt={pending.startedAt} />
            </div>
          )}
        </div>
      </div>

      {!atBottom && (
        <button
          onClick={() => scrollToBottom()}
          aria-label="Scroll to latest"
          className="animate-pop absolute bottom-4 left-1/2 grid h-9 w-9 -translate-x-1/2 rotate-180 place-items-center rounded-full border border-black/5 bg-white/90 text-zinc-600 shadow-xl backdrop-blur hover:text-accent-600 dark:border-white/10 dark:bg-zinc-900/90 dark:text-zinc-300"
        >
          <IconArrowUp size={16} />
        </button>
      )}
    </div>
  );
}

function previousUser(turns: Conversation["turns"], index: number): UserTurn | undefined {
  for (let i = index - 1; i >= 0; i -= 1) {
    const t = turns[i];
    if (t.role === "user") return t;
  }
  return undefined;
}

function UserBubble({ turn, onEdit }: { turn: UserTurn; onEdit: () => void }) {
  const copy = useCopy();
  return (
    <div className="animate-fade-up group flex flex-col items-end gap-1">
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-zinc-200/70 px-4 py-2.5 text-[15px] leading-relaxed text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100">
        <p className="whitespace-pre-wrap break-words">{turn.text}</p>
      </div>
      <div className="flex items-center gap-1 text-[11px] text-zinc-400 opacity-0 transition group-hover:opacity-100">
        {!turn.execute && <span className="mr-1 rounded bg-black/5 px-1.5 py-0.5 dark:bg-white/5">SQL only</span>}
        <MiniAction label="Copy" onClick={() => copy(turn.text)}>
          <IconCopy size={12} />
        </MiniAction>
        <MiniAction label="Edit" onClick={onEdit}>
          <IconPencil size={12} />
        </MiniAction>
      </div>
    </div>
  );
}

function ErrorCard({ turn, onRetry }: { turn: ErrorTurn; onRetry?: () => void }) {
  return (
    <div className="animate-fade-up flex gap-3">
      <div className="grid h-7 w-7 shrink-0 place-items-center rounded-[30%] bg-red-500/15 text-red-500">
        <IconAlert size={15} />
      </div>
      <div
        className={`flex flex-1 flex-wrap items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm ${
          turn.stopped
            ? "border-black/5 bg-white/60 text-zinc-500 dark:border-white/5 dark:bg-white/[0.03]"
            : "border-red-500/20 bg-red-500/[0.06] text-red-700 dark:text-red-300"
        }`}
      >
        <span>{turn.text}</span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1.5 rounded-lg border border-current/20 px-2.5 py-1 text-xs font-medium hover:bg-black/5 dark:hover:bg-white/10"
          >
            <IconRefresh size={12} /> Retry
          </button>
        )}
      </div>
    </div>
  );
}

function AssistantCard({
  turn,
  question,
  fresh,
  inspected,
  isLast,
  busy,
  onInspect,
  onFollowUp,
  onRegenerate,
}: {
  turn: AssistantTurn;
  question: UserTurn | undefined;
  fresh: boolean;
  inspected: boolean;
  isLast: boolean;
  busy: boolean;
  onInspect: (tab?: InspectorTab) => void;
  onFollowUp: (prompt: string, execute?: boolean) => void;
  onRegenerate?: () => void;
}) {
  const copy = useCopy();
  const r = turn.response;
  const text = assistantText(r);
  const { shown, done } = useTypewriter(text, fresh);
  const stats = headlineStats(r.result);
  const chart = chartSpec(r.result);
  const [view, setView] = useState<"table" | "chart">(chart ? "chart" : "table");
  const suggestions = isLast && !busy ? followUps(r, question) : [];
  const failed = r.status === "validation_failed" || r.status === "execution_failed";

  return (
    <div className="animate-fade-up flex gap-3">
      <div className="pt-0.5">
        <Logo size={28} />
      </div>
      <div className="min-w-0 flex-1 space-y-3">
        <div
          className={`overflow-hidden rounded-2xl rounded-tl-md border bg-white/70 shadow-sm backdrop-blur-xl transition dark:bg-white/[0.03] ${
            inspected
              ? "border-accent-400/40 dark:border-accent-400/30"
              : "border-black/5 dark:border-white/[0.06]"
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-3">
            <div className="flex items-center gap-2">
              <StatusBadge status={r.status} />
              {r.intent && (
                <span className="rounded-full bg-black/[0.04] px-2 py-0.5 font-mono text-[10px] text-zinc-500 dark:bg-white/[0.05]">
                  {r.intent}
                </span>
              )}
            </div>
            <PipelineTrace stages={turn.stages} elapsedMs={turn.elapsedMs} />
          </div>

          <div className="space-y-3 px-4 pb-4 pt-2.5">
            {r.interpreted_as && (
              <p className="flex items-start gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
                <IconSparkles size={12} className="mt-0.5 shrink-0 text-accent-500 dark:text-accent-400" />
                <span>
                  Interpreted as{" "}
                  <span className="font-medium text-zinc-700 dark:text-zinc-200">“{r.interpreted_as}”</span>
                </span>
              </p>
            )}
            <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-zinc-800 dark:text-zinc-100">
              {shown}
              {!done && <span className="animate-blink ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 bg-accent-500" />}
            </p>

            {done && (
              <div className="animate-fade-in space-y-3">
                {r.assumptions.length > 0 && (
                  <div className="rounded-xl border border-sky-500/15 bg-sky-500/[0.05] px-3 py-2 text-xs text-sky-800 dark:text-sky-200">
                    <p className="mb-1 flex items-center gap-1.5 font-semibold">
                      <IconInfo size={12} /> Assumptions
                    </p>
                    <ul className="list-disc space-y-0.5 pl-5">
                      {r.assumptions.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {failed && r.validation.issues.length > 0 && (
                  <ul className="space-y-1 rounded-xl border border-red-500/15 bg-red-500/[0.05] px-3 py-2 text-xs text-red-700 dark:text-red-300">
                    {r.validation.issues.map((issue, i) => (
                      <li key={i}>
                        <span className="font-mono font-semibold">{issue.code}</span> — {issue.message}
                      </li>
                    ))}
                  </ul>
                )}

                {r.sql && <SqlBlock sql={r.sql} collapseAfter={8} />}

                {stats && (
                  <div className="grid gap-2 sm:grid-cols-3">
                    {stats.map((stat) => (
                      <div
                        key={stat.label}
                        className="relative overflow-hidden rounded-xl border border-black/5 bg-zinc-50 px-4 py-3 dark:bg-white/[0.03] dark:border-white/[0.06]"
                      >
                        <p className="truncate font-mono text-[11px] text-zinc-500">{stat.label}</p>
                        <p className="text-3xl text-zinc-900 dark:text-white font-bold tracking-tight tabular-nums">{stat.value}</p>
                      </div>
                    ))}
                  </div>
                )}

                {r.result && !stats && (
                  <div className="space-y-2">
                    {chart && r.result.row_count > 0 && (
                      <div className="flex w-fit rounded-lg bg-black/[0.04] p-0.5 text-[11px] font-medium dark:bg-white/[0.05]">
                        {(["chart", "table"] as const).map((v) => (
                          <button
                            key={v}
                            onClick={() => setView(v)}
                            className={`flex items-center gap-1 rounded-md px-2 py-1 capitalize transition ${
                              view === v
                                ? "bg-white text-zinc-900 shadow-sm dark:bg-white/10 dark:text-white"
                                : "text-zinc-500"
                            }`}
                          >
                            {v === "chart" ? <IconChart size={12} /> : <IconTable size={12} />}
                            {v}
                          </button>
                        ))}
                      </div>
                    )}
                    {chart && view === "chart" ? (
                      <BarChart spec={chart} valueLabel={r.result.columns[chart.valueIndex]} limit={8} />
                    ) : (
                      <ResultsTable result={r.result} preview={5} />
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-black/5 bg-black/[0.015] px-3 py-1.5 dark:border-white/[0.05] dark:bg-white/[0.015]">
            <span className="px-1 text-[11px] text-zinc-400">
              {r.result
                ? `${r.result.row_count} row${r.result.row_count === 1 ? "" : "s"}${r.result.truncated ? "+" : ""} · ${r.result.duration_ms} ms`
                : r.sql
                  ? "Not executed"
                  : new Date(turn.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
            </span>
            <div className="flex items-center gap-0.5">
              <MiniAction label="Copy" onClick={() => copy(text, "Answer copied")}>
                <IconCopy size={13} />
              </MiniAction>
              {onRegenerate && !busy && (
                <MiniAction label="Regenerate" onClick={onRegenerate}>
                  <IconRefresh size={13} />
                </MiniAction>
              )}
              {(r.sql || r.result) && (
                <MiniAction label="Inspect" onClick={() => onInspect(r.result ? "results" : "sql")} showLabel>
                  <IconExpand size={13} />
                </MiniAction>
              )}
            </div>
          </div>
        </div>

        {suggestions.length > 0 && done && (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s, i) => (
              <button
                key={s.label}
                onClick={() => onFollowUp(s.prompt, s.execute)}
                style={{ animationDelay: `${i * 60}ms` }}
                className="animate-fade-up group flex items-center gap-1.5 rounded-full border border-black/5 bg-white/60 px-3 py-1.5 text-xs font-medium text-zinc-600 backdrop-blur transition hover:border-accent-400/50 hover:text-accent-700 dark:border-white/[0.07] dark:bg-white/[0.03] dark:text-zinc-300 dark:hover:text-accent-200"
              >
                <IconSparkles size={12} className="text-accent-500 dark:text-accent-400" />
                {s.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MiniAction({
  label,
  onClick,
  children,
  showLabel,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
  showLabel?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium text-zinc-400 transition hover:bg-black/5 hover:text-zinc-800 dark:hover:bg-white/10 dark:hover:text-white"
    >
      {children}
      {showLabel && label}
    </button>
  );
}
