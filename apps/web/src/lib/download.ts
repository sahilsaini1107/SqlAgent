import type { Conversation, ResultView } from "../types";

function triggerDownload(content: string, filename: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function downloadSql(sql: string): void {
  triggerDownload(sql, "query.sql", "text/sql");
}

function cellText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

// Escape a CSV cell, neutralising spreadsheet formula injection (cells starting with = + - @).
function escapeCsvCell(value: unknown): string {
  const text = cellText(value);
  const guarded = /^[=+\-@]/.test(text) ? `'${text}` : text;
  if (/[",\n\r]/.test(guarded)) {
    return `"${guarded.replace(/"/g, '""')}"`;
  }
  return guarded;
}

export function resultToCsv(result: ResultView): string {
  const header = result.columns.map(escapeCsvCell).join(",");
  const rows = result.rows.map((row) => row.map(escapeCsvCell).join(","));
  return [header, ...rows].join("\n");
}

export function resultToMarkdown(result: ResultView): string {
  const esc = (v: unknown) => cellText(v).replace(/\|/g, "\\|");
  const header = `| ${result.columns.map(esc).join(" | ")} |`;
  const divider = `| ${result.columns.map(() => "---").join(" | ")} |`;
  const rows = result.rows.map((row) => `| ${row.map(esc).join(" | ")} |`);
  return [header, divider, ...rows].join("\n");
}

export function resultToJson(result: ResultView): string {
  const records = result.rows.map((row) =>
    Object.fromEntries(result.columns.map((col, i) => [col, row[i]])),
  );
  return JSON.stringify(records, null, 2);
}

export function downloadResultCsv(result: ResultView): void {
  triggerDownload(resultToCsv(result), "results.csv", "text/csv");
}

export function downloadConversationMarkdown(conversation: Conversation): void {
  const parts = [`# ${conversation.title}`, ""];
  for (const turn of conversation.turns) {
    if (turn.role === "user") {
      parts.push(`**You:** ${turn.text}`, "");
    } else if (turn.role === "error") {
      parts.push(`> ${turn.text}`, "");
    } else {
      const r = turn.response;
      const text = r.explanation ?? r.clarification ?? r.refusal;
      if (text) parts.push(`**SQL Agent:** ${text}`, "");
      if (r.sql) parts.push("```sql", r.sql, "```", "");
      if (r.result && r.result.row_count > 0) parts.push(resultToMarkdown(r.result), "");
    }
  }
  const slug = conversation.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  triggerDownload(parts.join("\n"), `${slug || "conversation"}.md`, "text/markdown");
}
