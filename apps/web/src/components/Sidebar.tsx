import { useMemo, useState } from "react";

import { modKey } from "../hooks/useHotkeys";
import type { Conversation } from "../types";
import {
  IconChat,
  IconClose,
  IconMoon,
  IconPencil,
  IconPin,
  IconPlus,
  IconSearch,
  IconSun,
  IconTrash,
  Logo,
} from "./Icons";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  pendingId: string | null;
  online: boolean | null;
  dark: boolean;
  onToggleTheme: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRemove: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onTogglePin: (id: string) => void;
  onClose: () => void;
}

const DAY = 86_400_000;

function groupLabel(ts: number): string {
  const startOfToday = new Date().setHours(0, 0, 0, 0);
  if (ts >= startOfToday) return "Today";
  if (ts >= startOfToday - DAY) return "Yesterday";
  if (ts >= startOfToday - 7 * DAY) return "Previous 7 days";
  return "Older";
}

function queryCount(conversation: Conversation): number {
  return conversation.turns.filter((t) => t.role === "assistant" && t.response.sql).length;
}

export function Sidebar(props: Props) {
  const [query, setQuery] = useState("");

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 px-4 pb-3 pt-4">
        <div className="flex items-center gap-2.5">
          <Logo size={30} />
          <div className="leading-tight">
            <p className="text-[15px] font-semibold tracking-tight">SQL Agent</p>
            <p className="text-[11px] text-zinc-500">Natural language → SQL</p>
          </div>
        </div>
        <button
          onClick={props.onClose}
          aria-label="Close sidebar"
          className="rounded-lg p-1.5 text-zinc-500 hover:bg-black/5 lg:hidden dark:hover:bg-white/10"
        >
          <IconClose />
        </button>
      </div>

      <div className="px-3">
        <button
          onClick={props.onNew}
          className="group bg-brand relative flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl px-3 py-2.5 text-sm font-medium text-white shadow-sm transition active:scale-[0.98]"
        >
          <IconPlus size={16} strokeWidth={2.2} />
          New chat
          <kbd className="ml-auto rounded bg-white/15 px-1.5 py-0.5 font-sans text-[10px] font-medium">
            {modKey}⇧O
          </kbd>
        </button>
      </div>


      <div className="relative mx-3 mt-3">
        <IconSearch size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search chats…"
          className="w-full rounded-xl border border-black/5 bg-white/60 py-2 pl-8 pr-3 text-sm outline-none placeholder:text-zinc-400 focus:border-accent-400/60 focus:ring-2 focus:ring-accent-500/20 dark:border-white/5 dark:bg-white/5"
        />
      </div>

      <div className="mt-2 flex-1 overflow-y-auto px-2 pb-3">
        <ChatList {...props} query={query} />
      </div>

      <div className="flex items-center justify-between border-t border-black/5 px-4 py-3 text-xs dark:border-white/5">
        <span className="flex items-center gap-2 text-zinc-500">
          <span className="relative flex h-2 w-2">
            {props.online && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            )}
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${
                props.online === null ? "bg-zinc-400" : props.online ? "bg-emerald-400" : "bg-red-500"
              }`}
            />
          </span>
          {props.online === null ? "Connecting…" : props.online ? "Connected" : "API offline"}
        </span>
        <button
          onClick={props.onToggleTheme}
          aria-label="Toggle theme"
          className="rounded-lg p-1.5 text-zinc-500 transition hover:bg-black/5 hover:text-zinc-900 dark:hover:bg-white/10 dark:hover:text-white"
        >
          {props.dark ? <IconSun size={15} /> : <IconMoon size={15} />}
        </button>
      </div>
    </div>
  );
}

function ChatList({
  conversations,
  activeId,
  pendingId,
  onSelect,
  onRemove,
  onRename,
  onTogglePin,
  query,
}: Props & { query: string }) {
  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const visible = conversations
      .filter((c) => c.turns.length > 0)
      .filter(
        (c) =>
          !q ||
          c.title.toLowerCase().includes(q) ||
          c.turns.some((t) => t.role === "user" && t.text.toLowerCase().includes(q)),
      )
      .sort((a, b) => b.updatedAt - a.updatedAt);
    const map = new Map<string, Conversation[]>();
    for (const c of visible) {
      const label = c.pinned ? "Pinned" : groupLabel(c.updatedAt);
      map.set(label, [...(map.get(label) ?? []), c]);
    }
    const order = ["Pinned", "Today", "Yesterday", "Previous 7 days", "Older"];
    return order.filter((label) => map.has(label)).map((label) => ({ label, items: map.get(label)! }));
  }, [conversations, query]);

  if (groups.length === 0) {
    return (
      <div className="flex flex-col items-center px-4 py-10 text-center text-xs text-zinc-500">
        <div className="mb-3 grid h-10 w-10 place-items-center rounded-2xl bg-black/5 dark:bg-white/5">
          <IconChat size={18} />
        </div>
        {query ? "No chats match your search." : "Your conversations will show up here."}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {groups.map((group) => (
        <div key={group.label}>
          <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
            {group.label}
          </p>
          <ul className="space-y-0.5">
            {group.items.map((c) => (
              <ChatItem
                key={c.id}
                conversation={c}
                active={c.id === activeId}
                pending={c.id === pendingId}
                onSelect={() => onSelect(c.id)}
                onRemove={() => onRemove(c.id)}
                onRename={(title) => onRename(c.id, title)}
                onTogglePin={() => onTogglePin(c.id)}
              />
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function ChatItem({
  conversation,
  active,
  pending,
  onSelect,
  onRemove,
  onRename,
  onTogglePin,
}: {
  conversation: Conversation;
  active: boolean;
  pending: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onRename: (title: string) => void;
  onTogglePin: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [draft, setDraft] = useState(conversation.title);
  const queries = queryCount(conversation);

  const commit = () => {
    onRename(draft);
    setEditing(false);
  };

  return (
    <li className="group relative">
      {active && (
        <span className="bg-brand absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full" />
      )}
      {editing ? (
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") setEditing(false);
          }}
          className="w-full rounded-lg border border-accent-400/60 bg-white px-2.5 py-2 text-sm outline-none ring-2 ring-accent-500/20 dark:bg-zinc-900"
        />
      ) : (
        <button
          onClick={onSelect}
          onDoubleClick={() => {
            setDraft(conversation.title);
            setEditing(true);
          }}
          className={`flex w-full flex-col items-start rounded-lg px-2.5 py-2 text-left transition ${
            active
              ? "bg-accent-500/10 text-zinc-900 dark:bg-white/[0.07] dark:text-white"
              : "text-zinc-600 hover:bg-black/[0.04] dark:text-zinc-300 dark:hover:bg-white/[0.04]"
          }`}
        >
          <span className="flex w-full items-center gap-1.5 pr-16 text-sm">
            {conversation.pinned && <IconPin size={11} className="shrink-0 text-zinc-400" />}
            <span className="truncate">{conversation.title}</span>
          </span>
          <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-zinc-400">
            {pending ? (
              <span className="font-medium text-accent-600 dark:text-accent-400">Thinking…</span>
            ) : (
              <>
                {queries} {queries === 1 ? "query" : "queries"} ·{" "}
                {new Date(conversation.updatedAt).toLocaleTimeString([], {
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </>
            )}
          </span>
        </button>
      )}
      {!editing && (
        <div
          className={`absolute right-1.5 top-1.5 flex gap-0.5 rounded-md bg-white/90 p-0.5 shadow-sm backdrop-blur transition dark:bg-zinc-900/90 ${
            confirming ? "opacity-100" : "opacity-0 group-focus-within:opacity-100 group-hover:opacity-100"
          }`}
        >
          {confirming ? (
            <button
              onClick={onRemove}
              onBlur={() => setConfirming(false)}
              autoFocus
              className="rounded px-1.5 py-0.5 text-[11px] font-medium text-red-500 hover:bg-red-500/10"
            >
              Delete?
            </button>
          ) : (
            <>
              <ItemAction label={conversation.pinned ? "Unpin" : "Pin"} onClick={onTogglePin}>
                <IconPin size={13} />
              </ItemAction>
              <ItemAction
                label="Rename"
                onClick={() => {
                  setDraft(conversation.title);
                  setEditing(true);
                }}
              >
                <IconPencil size={13} />
              </ItemAction>
              <ItemAction label="Delete" onClick={() => setConfirming(true)}>
                <IconTrash size={13} />
              </ItemAction>
            </>
          )}
        </div>
      )}
    </li>
  );
}

function ItemAction({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      title={label}
      aria-label={label}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className="rounded p-1 text-zinc-400 hover:bg-black/5 hover:text-zinc-900 dark:hover:bg-white/10 dark:hover:text-white"
    >
      {children}
    </button>
  );
}
