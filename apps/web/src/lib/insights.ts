import type { ChatResponse, ResultView, UserTurn } from "../types";

export function isNumeric(value: unknown): boolean {
  if (typeof value === "number") return Number.isFinite(value);
  return typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value));
}

function isIdColumn(name: string): boolean {
  return /^id$|_id$/i.test(name);
}

function numericColumns(result: ResultView): number[] {
  return result.columns
    .map((_, index) => index)
    .filter((index) => {
      const values = result.rows.map((row) => row[index]).filter((v) => v !== null);
      return values.length > 0 && values.every(isNumeric);
    });
}

export interface ChartSpec {
  labelIndex: number;
  valueIndex: number;
  points: { label: string; value: number }[];
}

/** A bar chart makes sense for one label column against one numeric measure. */
export function chartSpec(result: ResultView | null): ChartSpec | null {
  if (!result || result.rows.length < 2 || result.rows.length > 40) return null;
  const numeric = numericColumns(result);
  const labelIndex = result.columns.findIndex((_, i) => !numeric.includes(i));
  const valueIndex = numeric.find((i) => !isIdColumn(result.columns[i])) ?? -1;
  if (labelIndex < 0 || valueIndex < 0) return null;
  return {
    labelIndex,
    valueIndex,
    points: result.rows.map((row) => ({
      label: row[labelIndex] === null ? "NULL" : String(row[labelIndex]),
      value: Number(row[valueIndex]),
    })),
  };
}

/** Single-row, single-or-few-column numeric answers read best as a headline number. */
export function headlineStats(result: ResultView | null): { label: string; value: string }[] | null {
  if (!result || result.rows.length !== 1 || result.columns.length > 3) return null;
  const row = result.rows[0];
  if (!row.every(isNumeric)) return null;
  return result.columns.map((label, i) => ({ label, value: formatNumber(Number(row[i])) }));
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
}

export interface FollowUp {
  label: string;
  prompt: string;
  /** Overrides the composer's "run" toggle for this follow-up. */
  execute?: boolean;
}

export function followUps(response: ChatResponse, question: UserTurn | undefined): FollowUp[] {
  if (response.status === "refused" || response.status === "clarification_required") return [];

  if (response.status === "answered" || response.intent === "explain" || response.intent === "sql_concept") {
    return [
      { label: "Show it on the sample data", prompt: "Write a query on this database that demonstrates that." },
      { label: "Give me a simpler explanation", prompt: "Explain that more simply, with a short example." },
    ];
  }

  const items: FollowUp[] = [];
  if (response.sql && !response.result && question && response.status === "validated") {
    items.push({ label: "Run this query", prompt: question.text, execute: true });
  }
  if (response.status === "validation_failed" || response.status === "execution_failed") {
    items.push({ label: "Try a simpler version", prompt: "Try a simpler version of that query." });
    return items;
  }

  const result = response.result;
  if (result && result.row_count > 0) {
    const numeric = numericColumns(result).filter((i) => !isIdColumn(result.columns[i]));
    if (numeric.length > 0) {
      const col = result.columns[numeric[0]];
      if (result.row_count > 3) items.push({ label: "Only the top 3", prompt: "Show only the top 3 of those." });
      items.push({ label: `Sort by ${col} ascending`, prompt: `Sort that by ${col} in ascending order.` });
    } else if (result.row_count > 1) {
      items.push({ label: "How many are there?", prompt: "How many rows does that return in total?" });
    }
  }
  if (response.sql) {
    items.push({ label: "Explain step by step", prompt: "Explain the previous query step by step." });
    items.push({ label: "Can it be optimized?", prompt: "Can the previous query be optimized?" });
  }
  return items.slice(0, 4);
}
