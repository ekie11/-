const BASE = "http://internal.invalid";

/** Возвращает безопасный внутренний путь для перехода после входа, иначе «/». */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/") || /[\u0000-\u001f\u007f\\]/.test(next)) return "/";
  try {
    const url = new URL(next, BASE);
    if (url.origin !== BASE) return "/";
    const out = url.pathname + url.search + url.hash;
    if (out.startsWith("//") || out.startsWith("/\\")) return "/";
    return out;
  } catch {
    return "/";
  }
}
