/** Возвращает безопасный внутренний путь для перехода после входа, иначе «/». */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/";
  return next;
}
