export type GroupId =
  | "page" | "body" | "headings" | "structure" | "numbering"
  | "captions" | "formulas" | "lists" | "sources" | "typography";

export const GROUPS: { id: GroupId; label: string }[] = [
  { id: "page", label: "Страница" },
  { id: "body", label: "Основной текст" },
  { id: "headings", label: "Заголовки" },
  { id: "structure", label: "Структура" },
  { id: "numbering", label: "Нумерация страниц" },
  { id: "captions", label: "Рисунки и таблицы" },
  { id: "formulas", label: "Формулы" },
  { id: "lists", label: "Списки" },
  { id: "sources", label: "Источники" },
  { id: "typography", label: "Типографика" },
];

export type FieldDef = {
  rule: string;
  path: string;
  group: GroupId;
  label: string;
  kind: "number" | "select" | "bool" | "text" | "fixed";
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: { value: string; label: string }[];
};

/** Подписи правил (строка правила в редакторе). */
export const RULE_LABELS: Record<string, string> = {
  "page.size": "Размер страницы",
  "page.margins": "Поля",
  "body.font_name": "Шрифт",
  "body.font_size": "Размер шрифта",
  "body.line_spacing": "Межстрочный интервал",
  "body.first_line_indent": "Абзацный отступ",
  "body.alignment": "Выравнивание текста",
  "headings.section": "Заголовки разделов",
  "headings.structural": "Структурные заголовки",
  "captions.figure": "Подпись рисунка",
  "captions.table": "Заголовок таблицы",
  "page_numbers": "Номер страницы",
  toc: "Оглавление",
};

const ALIGN = [
  { value: "justify", label: "по ширине" },
  { value: "left", label: "по левому краю" },
  { value: "center", label: "по центру" },
  { value: "right", label: "по правому краю" },
];

const mm = (rule: string, path: string, label: string): FieldDef => ({
  rule, path, group: "page", label, kind: "number", unit: "мм", min: 0, max: 50, step: 1,
});
const align = (rule: string, group: GroupId, label = "Выравнивание"): FieldDef => ({
  rule, path: "align", group, label, kind: "select", options: ALIGN,
});
const bool = (rule: string, path: string, group: GroupId, label: string): FieldDef => ({
  rule, path, group, label, kind: "bool",
});
const indent = (rule: string, path: string, group: GroupId, label: string): FieldDef => ({
  rule, path, group, label, kind: "number", unit: "см", min: 0, max: 3, step: 0.05,
});
const pt = (rule: string, path: string, label: string): FieldDef => ({
  rule, path, group: "body", label, kind: "number", unit: "пт", min: 8, max: 20, step: 0.5,
});

export const FIELDS: FieldDef[] = [
  {
    rule: "page.size", path: "format", group: "page", label: "Формат", kind: "fixed",
    options: [{ value: "A4", label: "A4" }],
  },
  {
    rule: "page.size", path: "orientation", group: "page", label: "Ориентация", kind: "select",
    options: [{ value: "portrait", label: "книжная" }, { value: "landscape", label: "альбомная" }],
  },
  mm("page.margins", "top_mm", "Верхнее поле"),
  mm("page.margins", "bottom_mm", "Нижнее поле"),
  mm("page.margins", "left_mm", "Левое поле"),
  mm("page.margins", "right_mm", "Правое поле"),
  { rule: "body.font_name", path: "name", group: "body", label: "Гарнитура", kind: "text" },
  pt("body.font_size", "min_pt", "Минимальный кегль"),
  pt("body.font_size", "target_pt", "Основной кегль"),
  {
    rule: "body.line_spacing", path: "multiple", group: "body", label: "Интервал", kind: "number",
    unit: "×", min: 1, max: 3, step: 0.05,
  },
  indent("body.first_line_indent", "cm", "body", "Отступ первой строки"),
  align("body.alignment", "body"),
  bool("headings.section", "bold", "headings", "Требовать жирный шрифт"),
  align("headings.section", "headings"),
  indent("headings.section", "first_line_indent_cm", "headings", "Отступ первой строки"),
  {
    rule: "headings.section", path: "trailing_period", group: "headings", label: "Точка в конце заголовка", kind: "fixed",
    options: [{ value: "false", label: "не ставится" }],
  },
  bool("headings.section", "page_break_before_level1", "headings", "Требовать начало раздела с новой страницы"),
  bool("headings.structural", "bold", "structure", "Требовать жирный шрифт"),
  align("headings.structural", "structure"),
  bool("headings.structural", "uppercase", "structure", "Требовать ПРОПИСНЫЕ буквы"),
  {
    rule: "headings.structural", path: "trailing_period", group: "structure", label: "Точка в конце заголовка", kind: "fixed",
    options: [{ value: "false", label: "не ставится" }],
  },
  bool("headings.structural", "page_break_before", "structure", "Требовать начало с новой страницы"),
  {
    rule: "toc", path: "levels", group: "structure", label: "Уровни оглавления", kind: "fixed",
    options: [{ value: "3", label: "3 уровня" }],
  },
  {
    rule: "toc", path: "hyperlinks", group: "structure", label: "Ссылки в оглавлении", kind: "fixed",
    options: [{ value: "true", label: "Да" }],
  },
  {
    rule: "page_numbers", path: "position", group: "numbering", label: "Положение", kind: "fixed",
    options: [{ value: "bottom_center", label: "внизу по центру" }],
  },
  bool("page_numbers", "show_on_first", "numbering", "Номер на первой странице"),
  { rule: "captions.figure", path: "pattern", group: "captions", label: "Шаблон подписи рисунка", kind: "text" },
  {
    rule: "captions.figure", path: "position", group: "captions", label: "Положение подписи рисунка", kind: "fixed",
    options: [{ value: "below", label: "под рисунком" }],
  },
  align("captions.figure", "captions", "Выравнивание подписи рисунка"),
  { rule: "captions.table", path: "pattern", group: "captions", label: "Шаблон заголовка таблицы", kind: "text" },
  {
    rule: "captions.table", path: "position", group: "captions", label: "Положение заголовка таблицы", kind: "fixed",
    options: [{ value: "above", label: "над таблицей" }],
  },
  align("captions.table", "captions", "Выравнивание заголовка таблицы"),
  indent("captions.table", "first_line_indent_cm", "captions", "Отступ заголовка таблицы"),
  {
    rule: "bibliography", path: "standard", group: "sources", label: "Стандарт оформления", kind: "fixed",
    options: [{ value: "7.0.100-2018", label: "ГОСТ Р 7.0.100-2018" }],
  },
  {
    rule: "bibliography", path: "order", group: "sources", label: "Порядок источников", kind: "fixed",
    options: [{ value: "mention", label: "по порядку упоминания" }],
  },
  {
    rule: "bibliography", path: "citation_format", group: "sources", label: "Формат ссылки", kind: "fixed",
    options: [{ value: "[N]", label: "[N]" }],
  },
];
