import { useState } from "react";

import { type ChartSpec, formatNumber } from "../lib/insights";

interface Props {
  spec: ChartSpec;
  valueLabel: string;
  /** Cap bars shown (preview inside a message). */
  limit?: number;
}

/** Horizontal single-series bar chart: one hue, labels in text ink, hover for exact values. */
export function BarChart({ spec, valueLabel, limit }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const points = limit ? spec.points.slice(0, limit) : spec.points;
  const max = Math.max(...points.map((p) => p.value), 0);
  const min = Math.min(...points.map((p) => p.value), 0);
  const span = max - min || 1;
  const zero = (-min / span) * 100;

  return (
    <figure className="space-y-1.5">
      <figcaption className="sr-only">
        {valueLabel} by {points.map((p) => p.label).join(", ")}
      </figcaption>
      {points.map((point, i) => {
        const width = (Math.abs(point.value) / span) * 100;
        const left = point.value >= 0 ? zero : zero - width;
        const active = hover === i;
        return (
          <div
            key={`${point.label}-${i}`}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            className="group grid grid-cols-[minmax(4rem,9rem)_1fr_auto] items-center gap-3 rounded-md px-1 py-0.5 text-xs"
          >
            <span className="truncate text-zinc-600 dark:text-zinc-300" title={point.label}>
              {point.label}
            </span>
            <div className="relative h-5">
              <div
                className={`absolute inset-y-[3px] rounded-[4px] bg-accent-500 dark:bg-accent-400 transition-[width,opacity] duration-700 ease-out ${
                  hover !== null && !active ? "opacity-40" : "opacity-100"
                }`}
                style={{
                  left: `${left}%`,
                  width: `${Math.max(width, 0.8)}%`,
                  animation: `fade-in 0.6s ${i * 40}ms both`,
                }}
              />
              {active && (
                <div className="animate-pop pointer-events-none absolute -top-8 z-10 whitespace-nowrap rounded-md bg-zinc-900 px-2 py-1 text-[11px] text-white shadow-xl dark:bg-white dark:text-zinc-900"
                  style={{ left: `${Math.min(left + width, 85)}%` }}
                >
                  {point.label}: <b>{formatNumber(point.value)}</b> {valueLabel}
                </div>
              )}
            </div>
            <span className="text-right font-mono tabular-nums text-zinc-500 dark:text-zinc-400">
              {formatNumber(point.value)}
            </span>
          </div>
        );
      })}
      {limit && spec.points.length > limit && (
        <p className="pl-1 text-[11px] text-zinc-400">+{spec.points.length - limit} more in the inspector</p>
      )}
    </figure>
  );
}
