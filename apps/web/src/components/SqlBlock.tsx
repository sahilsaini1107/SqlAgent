import Prism from "prismjs";
import "prismjs/components/prism-sql";
import { useMemo, useState } from "react";

import { useCopy } from "../hooks/useToast";
import { downloadSql } from "../lib/download";
import { IconChevron, IconCopy, IconDownload } from "./Icons";

interface Props {
  sql: string;
  /** Collapse to this many lines with an expand toggle; omit to always show everything. */
  collapseAfter?: number;
}

export function SqlBlock({ sql, collapseAfter }: Props) {
  const copy = useCopy();
  const lines = useMemo(
    () => sql.split("\n").map((line) => Prism.highlight(line || " ", Prism.languages.sql, "sql")),
    [sql],
  );
  const collapsible = collapseAfter !== undefined && lines.length > collapseAfter;
  const [expanded, setExpanded] = useState(false);
  const visible = collapsible && !expanded ? lines.slice(0, collapseAfter) : lines;

  return (
    <div className="group/sql overflow-hidden rounded-xl border border-white/[0.06] bg-[#111318] shadow-inner">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-3 py-1.5">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-zinc-500">
            sql
          </span>
        </div>
        <div className="flex gap-1">
          <CodeAction label="Copy" onClick={() => copy(sql, "SQL copied")}>
            <IconCopy size={13} />
          </CodeAction>
          <CodeAction label="Download" onClick={() => downloadSql(sql)}>
            <IconDownload size={13} />
          </CodeAction>
        </div>
      </div>
      <div className="relative">
        <pre className="m-0 overflow-x-auto py-3">
          <code className="language-sql grid">
            {visible.map((html, i) => (
              <span key={i} className="flex">
                <span className="w-10 shrink-0 select-none pr-3 text-right text-zinc-600">{i + 1}</span>
                <span className="pr-4 text-zinc-200" dangerouslySetInnerHTML={{ __html: html }} />
              </span>
            ))}
          </code>
        </pre>
        {collapsible && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className={`flex w-full items-center justify-center gap-1 py-1.5 text-[11px] font-medium text-zinc-400 hover:text-white ${
              expanded ? "border-t border-white/[0.06]" : "absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#111318] via-[#111318]/90 to-transparent pt-8"
            }`}
          >
            <IconChevron size={12} className={expanded ? "-rotate-90" : "rotate-90"} />
            {expanded ? "Collapse" : `Show all ${lines.length} lines`}
          </button>
        )}
      </div>
    </div>
  );
}

function CodeAction({
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
      onClick={onClick}
      title={label}
      className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-zinc-400 transition hover:bg-white/10 hover:text-white"
    >
      {children}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}
