function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function dateSuffix(): string {
  return new Date().toISOString().slice(0, 10);
}

export function exportCSV(data: Record<string, unknown>[], filename?: string) {
  if (data.length === 0) return;
  const keys = Object.keys(data[0]);
  const header = keys.map((k) => `"${k.replace(/"/g, '""')}"`).join(",");
  const rows = data.map((row) =>
    keys
      .map((k) => {
        const val = row[k];
        if (val === null || val === undefined) return "";
        const str = String(val);
        return `"${str.replace(/"/g, '""')}"`;
      })
      .join(",")
  );
  const csv = [header, ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  downloadBlob(blob, filename ?? `query-result-${dateSuffix()}.csv`);
}

export function exportJSON(data: Record<string, unknown>[], filename?: string) {
  if (data.length === 0) return;
  const json = JSON.stringify(data, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  downloadBlob(blob, filename ?? `query-result-${dateSuffix()}.json`);
}

export function exportSQL(sql: string, filename?: string) {
  const blob = new Blob([sql], { type: "application/sql" });
  downloadBlob(blob, filename ?? `query-${dateSuffix()}.sql`);
}

export function exportMarkdown(content: string, filename?: string) {
  const blob = new Blob([content], { type: "text/markdown" });
  downloadBlob(blob, filename ?? `report-${dateSuffix()}.md`);
}
