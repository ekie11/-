import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { FIELDS, GROUPS } from "./ruleSchema";

const PROFILES_DIR = path.resolve(__dirname, "../../../backend/profiles");

type Profile = { id: string; rules: Record<string, { value: Record<string, unknown> }> };

const profiles = readdirSync(PROFILES_DIR)
  .filter((f) => f.endsWith(".json"))
  .sort()
  .map((f) => ({
    file: f,
    profile: JSON.parse(readFileSync(path.join(PROFILES_DIR, f), "utf8")) as Profile,
  }));

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
  it("профили найдены", () => {
    expect(profiles.length).toBeGreaterThan(0);
  });
  it("10 групп в порядке из спецификации", () => {
    expect(GROUPS.map((g) => g.label)).toEqual([
      "Страница", "Основной текст", "Заголовки", "Структура", "Нумерация страниц",
      "Рисунки и таблицы", "Формулы", "Списки", "Источники", "Типографика",
    ]);
  });
  it.each(profiles.map((p) => [p.file, p.profile] as const))(
    "каждое поле указывает на существующий путь в %s",
    (_file, gost) => {
      for (const f of FIELDS) {
        expect(gost.rules[f.rule], f.rule).toBeDefined();
        expect(at(gost.rules[f.rule].value, f.path), `${f.rule}.${f.path}`).not.toBeUndefined();
      }
    },
  );
  it.each(profiles.map((p) => [p.file, p.profile] as const))(
    "каждый лист JSON описан полем в %s",
    (_file, gost) => {
      for (const [rule, cfg] of Object.entries(gost.rules)) {
        for (const leaf of leaves(cfg.value)) {
          expect(FIELDS.some((f) => f.rule === rule && f.path === leaf), `${rule}.${leaf}`).toBe(true);
        }
      }
    },
  );
  it.each(profiles.map((p) => [p.file, p.profile] as const))(
    "тип значения соответствует виду поля, группы существуют (%s)",
    (_file, gost) => {
      const ids = GROUPS.map((g) => g.id);
      for (const f of FIELDS) {
        expect(ids).toContain(f.group);
        const v = at(gost.rules[f.rule].value, f.path);
        if (f.kind === "number") expect(typeof v).toBe("number");
        if (f.kind === "bool") expect(typeof v).toBe("boolean");
        if (f.kind === "select" || f.kind === "fixed") expect(f.options?.map((o) => o.value)).toContain(String(v));
        if (f.kind === "text") expect(typeof v).toBe("string");
      }
    },
  );
  it("значения, которые движок не поддерживает, зафиксированы", () => {
    const fixed = FIELDS.filter((f) => f.kind === "fixed").map((f) => `${f.rule}.${f.path}=${f.options?.map((o) => o.value)}`);
    expect(fixed.sort()).toEqual([
      "bibliography.citation_format=[N]",
      "bibliography.standard=7.0.100-2018",
      "captions.figure.position=below",
      "captions.table.position=above",
      "headings.section.trailing_period=false",
      "headings.structural.trailing_period=false",
      "page.size.format=A4",
      "page_numbers.position=bottom_center",
    ]);
  });
});
