import { useEffect, useState } from "react";

import { IconCheck, IconWand } from "./Icons";

const STAGES: Record<string, { live: string; short: string }> = {
  // The stream only reports status changes, so this stage also covers drafting the SQL.
  classifying: { live: "Understanding your question and planning the query", short: "Understand" },
  generated: { live: "Writing SQL against the schema", short: "Generate" },
  validated: { live: "Validating — read-only, schema-checked", short: "Validate" },
  validation_failed: { live: "Repairing the query", short: "Repair" },
  executed: { live: "Running on the sample database", short: "Execute" },
  execution_failed: { live: "Execution hit an error", short: "Execute" },
  answered: { live: "Composing an answer", short: "Answer" },
  clarification_required: { live: "Needs a bit more detail", short: "Clarify" },
  refused: { live: "Checking the request", short: "Policy" },
};

function label(stage: string): { live: string; short: string } {
  return STAGES[stage] ?? { live: stage.replace(/_/g, " "), short: stage };
}

function useElapsed(startedAt: number): string {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(timer);
  }, []);
  return ((now - startedAt) / 1000).toFixed(1);
}

/** Live view of the agent graph while a request streams. */
export function PipelineLive({ stages, startedAt }: { stages: string[]; startedAt: number }) {
  const elapsed = useElapsed(startedAt);
  const steps = stages.length ? stages : ["classifying"];

  return (
    <div className="ring-glow is-active animate-fade-up w-full max-w-md rounded-2xl border border-black/5 bg-white/70 p-4 shadow-sm backdrop-blur-xl dark:border-white/[0.06] dark:bg-white/[0.03]">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-medium text-zinc-500">
          <span className="relative grid h-5 w-5 place-items-center">
            <span className="bg-brand absolute inset-0 animate-ping rounded-full opacity-30" />
            <span className="bg-brand relative h-2.5 w-2.5 rounded-full" />
          </span>
          Agent working
        </div>
        <span className="font-mono text-[11px] tabular-nums text-zinc-400">{elapsed}s</span>
      </div>
      <ol className="space-y-2">
        {steps.map((stage, i) => {
          const current = i === steps.length - 1;
          const repair = stage === "validation_failed";
          return (
            <li key={`${stage}-${i}`} className="animate-fade-up flex items-center gap-2.5 text-sm">
              <span
                className={`grid h-5 w-5 shrink-0 place-items-center rounded-full ${
                  current
                    ? "border-2 border-accent-400/40 border-t-accent-500"
                    : repair
                      ? "bg-amber-500/15 text-amber-500"
                      : "bg-emerald-500/15 text-emerald-500"
                } ${current ? "animate-spin" : ""}`}
              >
                {!current && (repair ? <IconWand size={11} /> : <IconCheck size={12} strokeWidth={2.6} />)}
              </span>
              <span className={current ? "shimmer-text font-medium" : "text-zinc-500 dark:text-zinc-400"}>
                {label(stage).live}
                {current && "…"}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** Compact record of the stages an answer went through. */
export function PipelineTrace({ stages, elapsedMs }: { stages: string[]; elapsedMs: number }) {
  if (stages.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1 text-[10px] font-medium text-zinc-400">
      {stages.map((stage, i) => (
        <span key={`${stage}-${i}`} className="flex items-center gap-1">
          {i > 0 && <span className="text-zinc-300 dark:text-zinc-600">›</span>}
          <span
            className={`rounded px-1.5 py-0.5 ${
              stage === "validation_failed" || stage === "execution_failed"
                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                : "bg-black/[0.04] dark:bg-white/[0.05]"
            }`}
          >
            {label(stage).short}
          </span>
        </span>
      ))}
      <span className="ml-1 font-mono tabular-nums">{(elapsedMs / 1000).toFixed(1)}s</span>
    </div>
  );
}
