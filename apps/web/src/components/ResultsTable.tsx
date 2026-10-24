import { useMemo, useState } from "react";

import { useCopy } from "../hooks/useToast";
import { downloadResultCsv, resultToCsv, resultToJson, resultToMarkdown } from "../lib/download";
import { isNumeric } from "../lib/insights";
import type { ResultView } from "../types";
import { IconChevron, IconDownload, IconSearch } from "./Icons";

interface Props {
  result: ResultView;
  /** Preview mode: first few rows, no toolbar. */
  preview?: number;
}

function compare(a: unknown, b: unknown): number {
  if (a === b) return 0;
  if (a === null || a === undefined) return 1;
  if (b === null || b === undefined) return -1;
  if (isNumeric(a) && isNumeric(b)) return Number(a) - Number(b);
  return String(a).localeCompare(String(b));
}

export function ResultsTable({ result, preview }: Props) {
  const copy = useCopy();
  const [sort, setSort] = useState<{ index: number; dir: 1 | -1 } | null>(null);
  const [filter, setFilter] = useState("");

  const numericCols = useMemo(
    () =>
      result.columns.map((_, i) => {
        const values = result.rows.map((r) => r[i]).filter((v) => v !== null);
        return values.length > 0 && values.every(isNumeric);
      }),
    [result],
  );

  const rows = useMemo(() => {
    const q = filter.trim().toLowerCase();
    let out = q
      ? result.rows.filter((row) => row.some((v) => String(v ?? "").toLowerCase().includes(q)))
      : result.rows;
    if (sort) out = [...out].sort((a, b) => compare(a[sort.index], b[sort.index]) * sort.dir);
    return preview ? out.slice(0, preview) : out;
  }, [result, filter, sort, preview]);

  if (result.row_count === 0) {
    return (
      <div className="rounded-xl border border-dashed border-black/10 px-4 py-6 text-center text-sm text-zinc-500 dark:border-white/10">
        The query ran fine but returned no rows.
      </div>
    );
  }

  const cycleSort = (index: number) =>
    setSort((s) => (s?.index !== index ? { index, dir: 1 } : s.dir === 1 ? { index, dir: -1 } : null));

  return (
    <div className="space-y-2">
      {!preview && (
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-40 flex-1">
            <IconSearch size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder={`Filter ${result.row_count} rows…`}
              className="w-full rounded-lg border border-black/5 bg-white/70 py-1.5 pl-7 pr-2 text-xs outline-none focus:border-accent-400/60 focus:ring-2 focus:ring-accent-500/20 dark:border-white/5 dark:bg-white/5"
            />
          </div>
          <div className="flex overflow-hidden rounded-lg border border-black/5 text-[11px] font-medium dark:border-white/10">
            {(
              [
                ["CSV", () => resultToCsv(result)],
                ["Markdown", () => resultToMarkdown(result)],
                ["JSON", () => resultToJson(result)],
              ] as const
            ).map(([label, fn]) => (
              <button
                key={label}
                onClick={() => copy(fn(), `Copied as ${label}`)}
                className="border-r border-black/5 px-2 py-1.5 text-zinc-500 transition last:border-r-0 hover:bg-accent-500/10 hover:text-accent-600 dark:border-white/10 dark:hover:text-accent-300"
              >
                {label}
              </button>
            ))}
          </div>
          <button
            onClick={() => downloadResultCsv(result)}
            className="flex items-center gap-1 rounded-lg border border-black/5 px-2 py-1.5 text-[11px] font-medium text-zinc-500 transition hover:bg-accent-500/10 hover:text-accent-600 dark:border-white/10 dark:hover:text-accent-300"
          >
            <IconDownload size={12} /> Download
          </button>
        </div>
      )}

      <div
        className={`overflow-auto rounded-xl border border-black/5 bg-white/60 dark:border-white/[0.06] dark:bg-white/[0.02] ${
          preview ? "" : "max-h-[60vh]"
        }`}
      >
        <table className="min-w-full text-left text-xs">
          <thead className="sticky top-0 z-10 bg-zinc-100/95 backdrop-blur dark:bg-zinc-900/95">
            <tr>
              {result.columns.map((col, i) => (
                <th
                  key={col}
                  className={`whitespace-nowrap px-3 py-2 font-semibold text-zinc-600 dark:text-zinc-300 ${
                    numericCols[i] ? "text-right" : ""
                  }`}
                >
                  <button
                    onClick={() => cycleSort(i)}
                    className={`inline-flex items-center gap-1 hover:text-accent-500 ${
                      numericCols[i] ? "flex-row-reverse" : ""
                    }`}
                  >
                    {col}
                    <IconChevron
                      size={11}
                      className={`transition ${
                        sort?.index === i
                          ? `text-accent-500 opacity-100 ${sort.dir === 1 ? "-rotate-90" : "rotate-90"}`
                          : "rotate-90 opacity-0"
                      }`}
                    />
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-black/[0.04] dark:divide-white/[0.04]">
            {rows.map((row, r) => (
              <tr key={r} className="transition hover:bg-accent-500/[0.05]">
                {row.map((value, c) => (
                  <td
                    key={c}
                    className={`whitespace-nowrap px-3 py-1.5 font-mono text-[12px] ${
                      numericCols[c] ? "text-right tabular-nums text-zinc-800 dark:text-zinc-100" : "text-zinc-700 dark:text-zinc-200"
                    }`}
                  >
                    {value === null || value === undefined ? (
                      <span className="rounded bg-zinc-500/10 px-1 text-[10px] italic text-zinc-400">NULL</span>
                    ) : (
                      String(value)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <p className="px-3 py-4 text-center text-xs text-zinc-500">No rows match “{filter}”.</p>
        )}
      </div>

      {result.truncated && !preview && (
        <p className="text-[11px] text-amber-600 dark:text-amber-400">
          Results were capped at the row limit — refine the question to narrow them down.
        </p>
      )}
    </div>
  );
}
