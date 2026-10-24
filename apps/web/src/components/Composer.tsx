import { forwardRef, useLayoutEffect, useRef } from "react";

import { modKey } from "../hooks/useHotkeys";
import type { Dialect } from "../types";
import { IconBolt, IconClose, IconPencil, IconSend, IconStop } from "./Icons";

const MAX_CHARS = 4000;

interface Props {
  value: string;
  onChange: (value: string) => void;
  execute: boolean;
  onExecuteChange: (execute: boolean) => void;
  dialect: Dialect;
  onDialectChange: (dialect: Dialect) => void;
  busy: boolean;
  editing: boolean;
  onSend: () => void;
  onStop: () => void;
  onCancelEdit: () => void;
  /** ArrowUp in an empty composer pulls the last question back for editing. */
  onRecallLast: () => void;
}

export const Composer = forwardRef<HTMLTextAreaElement, Props>(function Composer(props, ref) {
  const { value, onChange, execute, onExecuteChange, dialect, onDialectChange, busy, editing } =
    props;
  const innerRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto-grow up to ~8 lines.
  useLayoutEffect(() => {
    const el = innerRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [value]);

  const canSend = value.trim().length > 0 && value.length <= MAX_CHARS && !busy;

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (canSend) props.onSend();
    } else if (event.key === "Escape") {
      if (editing) props.onCancelEdit();
      else event.currentTarget.blur();
    } else if (event.key === "ArrowUp" && !value) {
      event.preventDefault();
      props.onRecallLast();
    }
  };

  return (
    <div className="px-4 pb-4 pt-2 sm:px-6">
      <div className="mx-auto max-w-3xl">
        {editing && (
          <div className="animate-fade-up mb-2 flex items-center justify-between rounded-xl border border-accent-400/30 bg-accent-500/10 px-3 py-1.5 text-xs text-accent-700 dark:text-accent-200">
            <span className="flex items-center gap-1.5">
              <IconPencil size={12} /> Editing — sending replaces that message and everything after it
            </span>
            <button onClick={props.onCancelEdit} aria-label="Cancel edit" className="rounded p-0.5 hover:bg-accent-500/20">
              <IconClose size={13} />
            </button>
          </div>
        )}

        <div
          className={`ring-glow rounded-2xl border border-black/5 bg-white/80 shadow-sm backdrop-blur-2xl transition dark:border-white/[0.08] dark:bg-zinc-900/70 ${
            busy ? "is-active" : ""
          }`}
        >
          <textarea
            ref={(el) => {
              innerRef.current = el;
              if (typeof ref === "function") ref(el);
              else if (ref) ref.current = el;
            }}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Ask anything about your data…  e.g. “Which customers spent the most last month?”"
            className="block max-h-[220px] w-full resize-none bg-transparent px-4 pb-2 pt-3.5 text-[15px] leading-relaxed outline-none placeholder:text-zinc-400"
          />
          <div className="flex items-center justify-between gap-2 px-3 pb-2.5">
            <div className="flex items-center gap-2">
            <button
              role="switch"
              aria-checked={execute}
              onClick={() => onExecuteChange(!execute)}
              title={execute ? "Queries run against the sample database" : "Only generate and validate SQL"}
              className={`flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                execute
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  : "border-black/10 text-zinc-500 dark:border-white/10"
              }`}
            >
              <span
                className={`relative h-3.5 w-6 rounded-full transition ${execute ? "bg-emerald-500" : "bg-zinc-300 dark:bg-zinc-600"}`}
              >
                <span
                  className={`absolute top-0.5 h-2.5 w-2.5 rounded-full bg-white shadow transition-all ${execute ? "left-3" : "left-0.5"}`}
                />
              </span>
              <IconBolt size={12} />
              {execute ? "Run on database" : "SQL only"}
            </button>
              <select
                value={dialect}
                onChange={(e) => onDialectChange(e.target.value as Dialect)}
                disabled={busy}
                title="SQL dialect to render the query in"
                aria-label="SQL dialect"
                className="cursor-pointer rounded-full border border-black/10 bg-transparent px-2.5 py-1 text-xs font-medium text-zinc-600 outline-none transition hover:bg-black/[0.03] disabled:opacity-50 dark:border-white/10 dark:text-zinc-300 dark:hover:bg-white/[0.04] [&>option]:bg-white [&>option]:text-zinc-800 dark:[&>option]:bg-zinc-800 dark:[&>option]:text-zinc-100"
              >
                <option value="sqlite">SQLite</option>
                <option value="postgres">PostgreSQL</option>
                <option value="mysql">MySQL</option>
              </select>
            </div>

            <div className="flex items-center gap-3">
              <span className="hidden text-[11px] text-zinc-400 sm:inline">
                {value.length > MAX_CHARS * 0.8 ? (
                  <span className={value.length > MAX_CHARS ? "text-red-500" : ""}>
                    {value.length}/{MAX_CHARS}
                  </span>
                ) : (
                  <>
                    <kbd className="font-sans">↵</kbd> send · <kbd className="font-sans">⇧↵</kbd> newline ·{" "}
                    <kbd className="font-sans">{modKey}K</kbd> commands
                  </>
                )}
              </span>
              {busy ? (
                <button
                  onClick={props.onStop}
                  aria-label="Stop"
                  className="grid h-9 w-9 place-items-center rounded-xl bg-zinc-900 text-white transition active:scale-95 dark:bg-white dark:text-zinc-900"
                >
                  <IconStop size={14} />
                </button>
              ) : (
                <button
                  onClick={props.onSend}
                  disabled={!canSend}
                  aria-label="Send"
                  className="bg-brand grid h-9 w-9 place-items-center rounded-xl text-white shadow-sm transition enabled:hover:bg-accent-700 enabled:active:scale-95 disabled:opacity-35"
                >
                  <IconSend size={16} strokeWidth={2.2} />
                </button>
              )}
            </div>
          </div>
        </div>
        <p className="mt-2 text-center text-[11px] text-zinc-400">
          Every query is validated as read-only before it touches the database.
        </p>
      </div>
    </div>
  );
});
