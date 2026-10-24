import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { Dialect } from "./types";

import { ChatThread } from "./components/ChatThread";
import { type Command, CommandPalette } from "./components/CommandPalette";
import { Composer } from "./components/Composer";
import { EXAMPLES, EmptyState } from "./components/EmptyState";
import {
  IconBolt,
  IconDownload,
  IconMoon,
  IconPanelRight,
  IconPlus,
  IconSearch,
  IconSidebar,
  IconSparkles,
  IconSun,
} from "./components/Icons";
import { Inspector, type InspectorTab } from "./components/Inspector";
import { Sidebar } from "./components/Sidebar";
import { useConversations } from "./hooks/useConversations";
import { useDarkMode } from "./hooks/useDarkMode";
import { type Hotkey, modKey, useHotkeys } from "./hooks/useHotkeys";
import { useToast } from "./hooks/useToast";
import { fetchHealth } from "./lib/api";
import { downloadConversationMarkdown } from "./lib/download";
import type { AssistantTurn, UserTurn } from "./types";

const isWide = (px: number) => typeof window !== "undefined" && window.matchMedia(`(min-width: ${px}px)`).matches;

function usePersistentFlag(key: string, initial: () => boolean): [boolean, (v: boolean | ((p: boolean) => boolean)) => void] {
  const [value, setValue] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(key);
      if (saved !== null) return saved === "1";
    } catch {
      // storage unavailable
    }
    return initial();
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, value ? "1" : "0");
    } catch {
      // storage unavailable
    }
  }, [key, value]);
  return [value, setValue];
}

export default function App() {
  const chat = useConversations();
  const { dark, toggle: toggleTheme } = useDarkMode();
  const toast = useToast();

  const [draft, setDraft] = useState("");
  const [execute, setExecute] = usePersistentFlag("sql-agent.execute", () => true);
  const [dialect, setDialect] = useState<Dialect>("sqlite");
  const [editingTurnId, setEditingTurnId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(() => isWide(1024));
  const [inspectorOpen, setInspectorOpen] = useState(() => isWide(1280));
  const [inspectedTurnId, setInspectedTurnId] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("results");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const check = () => fetchHealth().then(() => setOnline(true), () => setOnline(false));
    check();
    const timer = setInterval(check, 30_000);
    return () => clearInterval(timer);
  }, []);

  const active = chat.active;
  const busy = chat.pending !== null;

  const inspectedTurn = useMemo<AssistantTurn | null>(() => {
    if (!active) return null;
    const answers = active.turns.filter((t): t is AssistantTurn => t.role === "assistant");
    return answers.find((t) => t.id === inspectedTurnId) ?? answers[answers.length - 1] ?? null;
  }, [active, inspectedTurnId]);

  // A fresh answer takes over the inspector, on the most useful tab.
  useEffect(() => {
    if (!chat.freshTurnId) return;
    setInspectedTurnId(null);
    const turn = active?.turns.find((t) => t.id === chat.freshTurnId);
    if (turn?.role === "assistant") {
      setInspectorTab(turn.response.result ? "results" : turn.response.sql ? "sql" : "details");
    }
  }, [chat.freshTurnId]);

  const focusComposer = useCallback(() => {
    requestAnimationFrame(() => {
      const el = composerRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    });
  }, []);

  const closeSidebarOnMobile = () => {
    if (!isWide(1024)) setSidebarOpen(false);
  };

  const submit = (text: string, exec: boolean) => {
    if (!text.trim() || busy) return;
    void chat.send(text, exec, editingTurnId ? { replaceFrom: editingTurnId, dialect } : { dialect });
    setEditingTurnId(null);
    setDraft("");
  };

  const newChat = useCallback(() => {
    chat.newChat();
    setEditingTurnId(null);
    setInspectedTurnId(null);
    setDraft("");
    focusComposer();
  }, [chat, focusComposer]);

  const startEdit = (turn: UserTurn) => {
    setEditingTurnId(turn.id);
    setDraft(turn.text);
    setExecute(turn.execute);
    focusComposer();
  };

  const recallLast = () => {
    const last = active?.turns.filter((t): t is UserTurn => t.role === "user").pop();
    if (last && !busy) startEdit(last);
  };


  const exportChat = useCallback(() => {
    if (!active) return;
    downloadConversationMarkdown(active);
    toast("Conversation exported as Markdown");
  }, [active, toast]);

  const hotkeys = useMemo<Hotkey[]>(
    () => [
      { combo: "mod+k", handler: () => setPaletteOpen((v) => !v), allowInInput: true },
      { combo: "mod+shift+o", handler: newChat, allowInInput: true },
      { combo: "mod+b", handler: () => setSidebarOpen((v) => !v), allowInInput: true },
      { combo: "mod+i", handler: () => setInspectorOpen((v) => !v), allowInInput: true },
      { combo: "/", handler: focusComposer },
    ],
    [newChat, focusComposer],
  );
  useHotkeys(hotkeys);

  const commands = useMemo<Command[]>(() => {
    const actions: Command[] = [
      { id: "new", group: "Actions", label: "New chat", hint: `${modKey}⇧O`, icon: IconPlus, run: newChat },
      {
        id: "theme",
        group: "Actions",
        label: dark ? "Switch to light mode" : "Switch to dark mode",
        icon: dark ? IconSun : IconMoon,
        run: toggleTheme,
      },
      {
        id: "run",
        group: "Actions",
        label: execute ? "Switch to SQL-only mode" : "Run queries on the database",
        icon: IconBolt,
        run: () => setExecute((v) => !v),
      },
      { id: "sidebar", group: "Actions", label: "Toggle sidebar", hint: `${modKey}B`, icon: IconSidebar, run: () => setSidebarOpen((v) => !v) },
      { id: "inspector", group: "Actions", label: "Toggle inspector", hint: `${modKey}I`, icon: IconPanelRight, run: () => setInspectorOpen((v) => !v) },
    ];
    if (active) {
      actions.push({ id: "export", group: "Actions", label: "Export this chat as Markdown", icon: IconDownload, run: exportChat });
    }
    const examples: Command[] = EXAMPLES.map((e) => ({
      id: `ex-${e.prompt}`,
      group: "Try asking",
      label: e.prompt,
      icon: IconSparkles,
      run: () => void chat.send(e.prompt, execute, { fresh: true, dialect }),
    }));
    const chats: Command[] = chat.conversations
      .filter((c) => c.turns.length > 0)
      .map((c) => ({
        id: `chat-${c.id}`,
        group: "Chats",
        label: c.title,
        run: () => chat.select(c.id),
      }));
    return [...actions, ...examples, ...chats];
  }, [active, chat, dark, execute, exportChat, newChat, setExecute, toggleTheme]);

  return (
    <div className="relative flex h-full overflow-hidden">
      {sidebarOpen && (
        <div className="animate-fade-in fixed inset-0 z-30 bg-zinc-950/40 backdrop-blur-sm lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-72 shrink-0 border-r border-black/5 bg-white/80 backdrop-blur-2xl transition-[transform,margin] duration-300 ease-out lg:relative lg:z-10 lg:bg-white/40 dark:border-white/[0.06] dark:bg-zinc-950/80 lg:dark:bg-white/[0.02] ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:-ml-72"
        }`}
      >
        <Sidebar
          conversations={chat.conversations}
          activeId={chat.activeId}
          pendingId={chat.pending?.conversationId ?? null}
          online={online}
          dark={dark}
          onToggleTheme={toggleTheme}
          onSelect={(id) => {
            chat.select(id);
            setEditingTurnId(null);
            setInspectedTurnId(null);
            closeSidebarOnMobile();
          }}
          onNew={() => {
            newChat();
            closeSidebarOnMobile();
          }}
          onRemove={chat.remove}
          onRename={chat.rename}
          onTogglePin={chat.togglePin}
          onClose={() => setSidebarOpen(false)}
        />
      </aside>

      <main className="relative z-10 flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 px-3 sm:px-4">
          <HeaderButton label={`Toggle sidebar (${modKey}B)`} onClick={() => setSidebarOpen((v) => !v)}>
            <IconSidebar size={17} />
          </HeaderButton>
          {!sidebarOpen && (
            <HeaderButton label="New chat" onClick={newChat}>
              <IconPlus size={17} />
            </HeaderButton>
          )}
          <h2 className="min-w-0 flex-1 truncate px-1 text-sm font-medium text-zinc-700 dark:text-zinc-200">
            {active?.title ?? <span className="text-zinc-400">New conversation</span>}
          </h2>
          <button
            onClick={() => setPaletteOpen(true)}
            className="hidden items-center gap-2 rounded-xl border border-black/5 bg-white/50 py-1.5 pl-2.5 pr-1.5 text-xs text-zinc-400 backdrop-blur transition hover:border-accent-400/40 hover:text-zinc-600 sm:flex dark:border-white/[0.07] dark:bg-white/[0.03] dark:hover:text-zinc-200"
          >
            <IconSearch size={13} />
            Search or jump to…
            <kbd className="rounded-md bg-black/5 px-1.5 py-0.5 font-sans text-[10px] dark:bg-white/10">{modKey} K</kbd>
          </button>
          {active && (
            <HeaderButton label="Export chat" onClick={exportChat}>
              <IconDownload size={17} />
            </HeaderButton>
          )}
          <HeaderButton
            label={`Toggle inspector (${modKey}I)`}
            onClick={() => setInspectorOpen((v) => !v)}
            active={inspectorOpen}
          >
            <IconPanelRight size={17} />
          </HeaderButton>
        </header>

        {active ? (
          <ChatThread
            conversation={active}
            pending={chat.pending}
            freshTurnId={chat.freshTurnId}
            inspectedTurnId={inspectorOpen ? (inspectedTurn?.id ?? null) : null}
            onInspect={(turnId, tab) => {
              setInspectedTurnId(turnId);
              if (tab) setInspectorTab(tab);
              setInspectorOpen(true);
            }}
            onFollowUp={(prompt, exec) => submit(prompt, exec ?? execute)}
            onResend={(turn) => void chat.send(turn.text, turn.execute, { replaceFrom: turn.id, dialect })}
            onEdit={startEdit}
          />
        ) : (
          <EmptyState onExample={(p) => submit(p, execute)} />
        )}

        <Composer
          ref={composerRef}
          value={draft}
          onChange={setDraft}
          execute={execute}
          onExecuteChange={setExecute}
          dialect={dialect}
          onDialectChange={setDialect}
          busy={busy}
          editing={editingTurnId !== null}
          onSend={() => submit(draft, execute)}
          onStop={chat.stop}
          onCancelEdit={() => {
            setEditingTurnId(null);
            setDraft("");
          }}
          onRecallLast={recallLast}
        />
      </main>

      {inspectorOpen && (
        <div className="animate-fade-in fixed inset-0 z-30 bg-zinc-950/40 backdrop-blur-sm xl:hidden" onClick={() => setInspectorOpen(false)} />
      )}
      <aside
        className={`fixed inset-y-0 right-0 z-40 w-[min(100vw,460px)] shrink-0 border-l border-black/5 bg-white/90 backdrop-blur-2xl transition-[transform,margin] duration-300 ease-out xl:relative xl:z-10 xl:bg-white/40 dark:border-white/[0.06] dark:bg-zinc-950/90 xl:dark:bg-white/[0.02] ${
          inspectorOpen ? "translate-x-0" : "translate-x-full xl:-mr-[460px]"
        }`}
      >
        <Inspector
          turn={inspectedTurn}
          tab={inspectorTab}
          onTab={setInspectorTab}
          onClose={() => setInspectorOpen(false)}
        />
      </aside>

      <CommandPalette open={paletteOpen} commands={commands} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}

function HeaderButton({
  label,
  onClick,
  active,
  children,
}: {
  label: string;
  onClick: () => void;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl transition ${
        active
          ? "bg-accent-500/10 text-accent-600 dark:text-accent-300"
          : "text-zinc-500 hover:bg-black/5 hover:text-zinc-900 dark:hover:bg-white/10 dark:hover:text-white"
      }`}
    >
      {children}
    </button>
  );
}
