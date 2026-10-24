import { useEffect, useMemo, useRef, useState } from "react";

import { IconChat, IconCommand, IconSearch } from "./Icons";

export interface Command {
  id: string;
  label: string;
  group: string;
  hint?: string;
  icon?: React.ComponentType<{ size?: number }>;
  run: () => void;
}

interface Props {
  open: boolean;
  commands: Command[];
  onClose: () => void;
}

export function CommandPalette({ open, commands, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setIndex(0);
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => `${c.label} ${c.group}`.toLowerCase().includes(q));
  }, [commands, query]);

  useEffect(() => setIndex(0), [query]);

  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${index}"]`)?.scrollIntoView({ block: "nearest" });
  }, [index]);

  if (!open) return null;

  const run = (command: Command | undefined) => {
    if (!command) return;
    onClose();
    command.run();
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      run(filtered[index]);
    } else if (event.key === "Escape") {
      onClose();
    }
  };

  let lastGroup = "";

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center p-4 pt-[12vh]" onKeyDown={onKeyDown}>
      <div className="animate-fade-in absolute inset-0 bg-zinc-950/40 backdrop-blur-sm" onClick={onClose} />
      <div
        role="dialog"
        aria-label="Command palette"
        className="animate-pop relative w-full max-w-xl overflow-hidden rounded-2xl border border-black/5 bg-white/95 shadow-2xl backdrop-blur-2xl dark:border-white/10 dark:bg-zinc-900/95"
      >
        <div className="flex items-center gap-3 border-b border-black/5 px-4 dark:border-white/10">
          <IconSearch size={16} className="text-zinc-400" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats, actions, examples…"
            className="flex-1 bg-transparent py-4 text-[15px] outline-none placeholder:text-zinc-400"
          />
          <kbd className="rounded border border-black/10 px-1.5 py-0.5 text-[10px] text-zinc-400 dark:border-white/10">
            Esc
          </kbd>
        </div>
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto p-2">
          {filtered.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-zinc-500">No results for “{query}”.</p>
          )}
          {filtered.map((command, i) => {
            const header = command.group !== lastGroup ? command.group : null;
            lastGroup = command.group;
            const Icon = command.icon ?? (command.group === "Chats" ? IconChat : IconCommand);
            return (
              <div key={command.id}>
                {header && (
                  <p className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                    {header}
                  </p>
                )}
                <button
                  data-index={i}
                  onMouseMove={() => setIndex(i)}
                  onClick={() => run(command)}
                  className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${
                    i === index
                      ? "bg-accent-500/10 text-accent-700 dark:bg-white/[0.07] dark:text-white"
                      : "text-zinc-600 dark:text-zinc-300"
                  }`}
                >
                  <span className={i === index ? "text-accent-500" : "text-zinc-400"}>
                    <Icon size={15} />
                  </span>
                  <span className="flex-1 truncate">{command.label}</span>
                  {command.hint && <span className="text-[11px] text-zinc-400">{command.hint}</span>}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
