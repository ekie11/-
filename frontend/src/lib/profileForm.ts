import type { Profile } from "./api";
import { FIELDS, type GroupId } from "./ruleSchema";

export function getAt(value: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>(
    (o, k) => (o !== null && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined),
    value,
  );
}

export function setAt(value: unknown, path: string, v: unknown): unknown {
  const [head, ...rest] = path.split(".");
  const obj = (value !== null && typeof value === "object" ? value : {}) as Record<string, unknown>;
  return { ...obj, [head]: rest.length ? setAt(obj[head], rest.join("."), v) : v };
}

function equal(a: unknown, b: unknown): boolean {
  return JSON.stringify(a, sortKeys) === JSON.stringify(b, sortKeys);
}
function sortKeys(_: string, v: unknown) {
  if (v !== null && typeof v === "object" && !Array.isArray(v)) {
    return Object.fromEntries(Object.entries(v).sort(([x], [y]) => x.localeCompare(y)));
  }
  return v;
}

/** Правило отличается от базового (значение, важность, включённость). Без базы — нет отличий. */
export function differs(rule: unknown, baseRule: unknown): boolean {
  if (baseRule === undefined) return false;
  return !equal(rule, baseRule);
}

export function groupHasDiff(profile: Pick<Profile, "rules">, base: Pick<Profile, "rules"> | null, group: GroupId): boolean {
  if (!base) return false;
  const rules = new Set(FIELDS.filter((f) => f.group === group).map((f) => f.rule));
  return [...rules].some((r) => differs(profile.rules[r], base.rules[r]));
}

export function unknownRules(profile: Pick<Profile, "rules">): string[] {
  const known = new Set(FIELDS.map((f) => f.rule));
  return Object.keys(profile.rules).filter((r) => !known.has(r));
}
