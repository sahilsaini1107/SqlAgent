const STATUS_STYLES: Record<string, { label: string; className: string }> = {
  validated: { label: "Validated", className: "text-emerald-600 bg-emerald-500/10 dark:text-emerald-300" },
  executed: { label: "Executed", className: "text-emerald-600 bg-emerald-500/10 dark:text-emerald-300" },
  validation_failed: { label: "Validation failed", className: "text-red-600 bg-red-500/10 dark:text-red-300" },
  execution_failed: { label: "Execution failed", className: "text-red-600 bg-red-500/10 dark:text-red-300" },
  clarification_required: {
    label: "Needs clarification",
    className: "text-amber-700 bg-amber-500/10 dark:text-amber-300",
  },
  refused: { label: "Refused", className: "text-zinc-600 bg-zinc-500/10 dark:text-zinc-300" },
  answered: { label: "Answered", className: "text-sky-600 bg-sky-500/10 dark:text-sky-300" },
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? {
    label: status,
    className: "text-zinc-600 bg-zinc-500/10 dark:text-zinc-300",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ${style.className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {style.label}
    </span>
  );
}
