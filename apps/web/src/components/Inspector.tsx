import { useCopy } from "../hooks/useToast";
import { chartSpec } from "../lib/insights";
import type { AssistantTurn, ValidationIssue } from "../types";
import { BarChart } from "./BarChart";
import { IconChart, IconClose, IconCode, IconCopy, IconInfo, IconShield, IconTable } from "./Icons";
import { PipelineTrace } from "./Pipeline";
import { ResultsTable } from "./ResultsTable";
import { SqlBlock } from "./SqlBlock";
import { StatusBadge } from "./StatusBadge";

export type InspectorTab = "results" | "chart" | "sql" | "details";

interface Props {
  turn: AssistantTurn | null;
  tab: InspectorTab;
  onTab: (tab: InspectorTab) => void;
  onClose: () => void;
}

const TABS: { id: InspectorTab; label: string; icon: typeof IconTable }[] = [
  { id: "results", label: "Results", icon: IconTable },
  { id: "chart", label: "Chart", icon: IconChart },
  { id: "sql", label: "SQL", icon: IconCode },
  { id: "details", label: "Details", icon: IconInfo },
];

export function Inspector({ turn, tab, onTab, onClose }: Props) {
  const r = turn?.response ?? null;
  const chart = chartSpec(r?.result ?? null);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 px-4 pb-2 pt-4">
        <div>
          <p className="text-sm font-semibold">Inspector</p>
          <p className="text-[11px] text-zinc-500">
            {r ? "Selected answer — click any answer to inspect it" : "Nothing selected yet"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {r && <StatusBadge status={r.status} />}
          <button
            onClick={onClose}
            aria-label="Close inspector"
            className="rounded-lg p-1.5 text-zinc-500 hover:bg-black/5 dark:hover:bg-white/10"
          >
            <IconClose />
          </button>
        </div>
      </div>

      <div className="mx-4 grid grid-cols-4 rounded-xl bg-black/5 p-1 text-xs font-medium dark:bg-white/5">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onTab(id)}
            className={`flex items-center justify-center gap-1.5 rounded-lg py-1.5 transition ${
              tab === id
                ? "bg-white text-zinc-900 shadow-sm dark:bg-white/10 dark:text-white"
                : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            }`}
          >
            <Icon size={13} />
            <span className="hidden xl:inline">{label}</span>
          </button>
        ))}
      </div>

      <div key={`${turn?.id}-${tab}`} className="animate-fade-in flex-1 overflow-y-auto p-4">
        {!r ? (
          <Empty
            title="Ask something to get started"
            text="Generated SQL, full results, a chart, and validation details for any answer show up here."
          />
        ) : tab === "results" ? (
          r.result ? (
            <ResultsTable result={r.result} />
          ) : (
            <Empty
              title="Not executed"
              text={r.sql ? "Turn on “Run” in the composer and ask again to execute this SQL." : "This answer has no query to run."}
            />
          )
        ) : tab === "chart" ? (
          chart && r.result ? (
            <div className="rounded-xl border border-black/5 bg-white/60 p-4 dark:border-white/[0.06] dark:bg-white/[0.02]">
              <p className="mb-3 text-xs font-medium text-zinc-500">
                <span className="font-mono text-zinc-800 dark:text-zinc-200">{r.result.columns[chart.valueIndex]}</span>{" "}
                by <span className="font-mono text-zinc-800 dark:text-zinc-200">{r.result.columns[chart.labelIndex]}</span>
              </p>
              <BarChart spec={chart} valueLabel={r.result.columns[chart.valueIndex]} />
            </div>
          ) : (
            <Empty
              title="No chart for this result"
              text="Charts appear when a result has one label column and one numeric column with 2–40 rows."
            />
          )
        ) : tab === "sql" ? (
          r.sql ? (
            <div className="space-y-3">
              <p className="text-[11px] text-zinc-500">
                Dialect:{" "}
                <span className="font-mono text-zinc-700 dark:text-zinc-300">{r.dialect}</span>
              </p>
              <SqlBlock sql={r.sql} />
              {r.plan && r.plan.length > 0 && <QueryPlan steps={r.plan} />}
            </div>
          ) : (
            <Empty title="No SQL" text="This answer didn't need a query." />
          )
        ) : (
          <Details turn={turn!} />
        )}
      </div>
    </div>
  );
}

function Details({ turn }: { turn: AssistantTurn }) {
  const copy = useCopy();
  const r = turn.response;
  return (
    <div className="space-y-4 text-sm">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-xl border border-black/5 bg-white/60 p-3 text-xs dark:border-white/[0.06] dark:bg-white/[0.02]">
        <dt className="text-zinc-500">Intent</dt>
        <dd className="font-mono">{r.intent ?? "—"}</dd>
        <dt className="text-zinc-500">Status</dt>
        <dd className="font-mono">{r.status}</dd>
        <dt className="text-zinc-500">Latency</dt>
        <dd className="font-mono">{(turn.elapsedMs / 1000).toFixed(2)}s end-to-end</dd>
        <dt className="text-zinc-500">Trace</dt>
        <dd>
          <button
            onClick={() => copy(r.trace_id, "Trace id copied")}
            className="flex max-w-full items-center gap-1 truncate font-mono hover:text-accent-500"
          >
            <span className="truncate">{r.trace_id}</span>
            <IconCopy size={11} className="shrink-0" />
          </button>
        </dd>
      </dl>

      <section>
        <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Pipeline</h4>
        <PipelineTrace stages={turn.stages} elapsedMs={turn.elapsedMs} />
      </section>

      <section>
        <h4 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
          <IconShield size={12} /> Validation
        </h4>
        <p
          className={`mb-2 text-xs font-medium ${r.validation.passed ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}
        >
          {r.validation.passed ? "Passed every read-only and schema check." : "Failed validation."}
        </p>
        <Issues items={r.validation.issues} tone="error" />
        <Issues items={r.validation.warnings} tone="warning" />
      </section>

      {r.assumptions.length > 0 && (
        <section>
          <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Assumptions</h4>
          <ul className="list-disc space-y-1 pl-5 text-xs text-zinc-600 dark:text-zinc-300">
            {r.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function Issues({ items, tone }: { items: ValidationIssue[]; tone: "error" | "warning" }) {
  if (items.length === 0) return null;
  const color =
    tone === "error"
      ? "border-red-500/15 bg-red-500/[0.05] text-red-700 dark:text-red-300"
      : "border-amber-500/15 bg-amber-500/[0.05] text-amber-700 dark:text-amber-300";
  return (
    <ul className={`mb-2 space-y-1 rounded-xl border px-3 py-2 text-xs ${color}`}>
      {items.map((issue, i) => (
        <li key={i}>
          <span className="font-mono font-semibold">{issue.code}</span> — {issue.message}
        </li>
      ))}
    </ul>
  );
}

function QueryPlan({ steps }: { steps: string[] }) {
  return (
    <section className="rounded-xl border border-black/5 bg-white/60 p-3 dark:border-white/[0.06] dark:bg-white/[0.02]">
      <h4 className="mb-2 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
        <span>Query plan</span>
        <span className="font-mono normal-case text-zinc-500">SQLite engine</span>
      </h4>
      <ul className="space-y-1 font-mono text-[11px] text-zinc-600 dark:text-zinc-300">
        {steps.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ul>
    </section>
  );
}


function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <div className="bg-brand mb-4 grid h-12 w-12 place-items-center rounded-2xl text-white opacity-80 shadow-sm">
        <IconTable size={20} />
      </div>
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 max-w-xs text-xs leading-relaxed text-zinc-500">{text}</p>
    </div>
  );
}
