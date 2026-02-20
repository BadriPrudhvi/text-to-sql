import { createHighlighterCore, type HighlighterCore } from "shiki/core";
import { createJavaScriptRegexEngine } from "shiki/engine/javascript";

let highlighter: HighlighterCore | null = null;
let loading: Promise<HighlighterCore> | null = null;

/**
 * Returns a shared Shiki highlighter loaded with only the SQL grammar
 * and github-light theme. Uses the JS regex engine (no WASM needed).
 */
export function getHighlighter(): Promise<HighlighterCore> {
  if (highlighter) return Promise.resolve(highlighter);
  if (loading) return loading;

  loading = createHighlighterCore({
    themes: [import("@shikijs/themes/github-light")],
    langs: [import("@shikijs/langs/sql")],
    engine: createJavaScriptRegexEngine(),
  }).then((h) => {
    highlighter = h;
    return h;
  }).catch((err) => {
    loading = null;
    throw err;
  });

  return loading;
}

/** Highlight SQL code to HTML using the shared lightweight highlighter. */
export async function highlightSQL(code: string): Promise<string> {
  const h = await getHighlighter();
  return h.codeToHtml(code, { lang: "sql", theme: "github-light" });
}
