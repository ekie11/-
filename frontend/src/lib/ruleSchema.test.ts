import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { FIELDS, GROUPS } from "./ruleSchema";

const gost = JSON.parse(
  readFileSync(path.resolve(__dirname, "../../../backend/profiles/gost_7_32_2017.json"), "utf8"),
) as { rules: Record<string, { value: Record<string, unknown> }> };

function leaves(v: unknown, prefix = ""): string[] {
  if (v !== null && typeof v === "object" && !Array.isArray(v)) {
    return Object.entries(v).flatMap(([k, x]) => leaves(x, prefix ? `${prefix}.${k}` : k));
  }
  return [prefix];
}

function at(v: unknown, p: string): unknown {
  return p.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], v);
}

describe("ruleSchema", () => {
  it("10 групп в порядке из спецификации", () => {
    expect(GROUPS.map((g) => g.label)).toEqual([
      "Страница", "Основной текст", "Заголовки", "Структура", "Нумерация страниц",
      "Рисунки и таблицы", "Формулы", "Списки", "Источники", "Типографика",
    ]);
  });
  it("каждое поле указывает на существующий путь в ГОСТ-профиле", () => {
    for (const f of FIELDS) {
      expect(gost.rules[f.rule], f.rule).toBeDefined();
      expect(at(gost.rules[f.rule].value, f.path), `${f.rule}.${f.path}`).not.toBeUndefined();
    }
  });
  it("каждый лист JSON описан полем", () => {
    for (const [rule, cfg] of Object.entries(gost.rules)) {
      for (const leaf of leaves(cfg.value)) {
        expect(FIELDS.some((f) => f.rule === rule && f.path === leaf), `${rule}.${leaf}`).toBe(true);
      }
    }
  });
  it("тип значения соответствует виду поля, группы существуют", () => {
    const ids = GROUPS.map((g) => g.id);
    for (const f of FIELDS) {
      expect(ids).toContain(f.group);
      const v = at(gost.rules[f.rule].value, f.path);
      if (f.kind === "number") expect(typeof v).toBe("number");
      if (f.kind === "bool") expect(typeof v).toBe("boolean");
      if (f.kind === "select") expect(f.options?.map((o) => o.value)).toContain(v);
      if (f.kind === "text") expect(typeof v).toBe("string");
    }
  });
});
