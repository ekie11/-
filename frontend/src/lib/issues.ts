import type { Issue, JobMode, Report } from "./api";

export interface IssueGroup {
  rule: string;
  source: string;
  items: Issue[];
}

export function groupIssues(issues: Issue[]): IssueGroup[] {
  const map = new Map<string, IssueGroup>();
  for (const it of issues) {
    const rule = it.rule ?? "";
    let g = map.get(rule);
    if (!g) {
      g = { rule, source: it.source ?? "", items: [] };
      map.set(rule, g);
    }
    g.items.push(it);
  }
  return [...map.values()];
}

export function plural(n: number): string {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return "замечание";
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return "замечания";
  return "замечаний";
}

export function issueCount(report: Report): number {
  const s = report.summary;
  if (s && (s.errors !== undefined || s.recommendations !== undefined)) {
    return (s.errors ?? 0) + (s.recommendations ?? 0);
  }
  return report.issues?.length ?? 0;
}

export function summary(report: Report, mode: JobMode): string {
  const n = issueCount(report);
  if (mode === "check") return n === 0 ? "Замечаний нет" : `${n} ${plural(n)}`;
  if (n === 0) return "Оформление готово. Замечаний не осталось";
  const which = plural(n) === "замечание" ? "которое" : "которые";
  return `Оформление готово. Осталось ${n} ${plural(n)}, ${which} нужно поправить вручную`;
}

const RULE_TITLES: Record<string, string> = {
  "page.size": "Формат страницы",
  "page.margins": "Поля",
  "body.font_name": "Шрифт",
  "body.font_size": "Размер шрифта",
  "body.line_spacing": "Межстрочный интервал",
  "body.first_line_indent": "Абзацный отступ",
  "body.alignment": "Выравнивание текста",
  "headings.section": "Заголовки разделов",
  "headings.structural": "Структурные элементы",
  "captions.figure": "Подписи рисунков",
  "captions.table": "Подписи таблиц",
  page_numbers: "Нумерация страниц",
  bibliography: "Список источников",
  toc: "Оглавление",
};

export function ruleTitle(rule: string): string {
  return RULE_TITLES[rule] ?? rule;
}
