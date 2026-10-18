import { describe, expect, it } from "vitest";
import type { Profile } from "./api";
import { differs, getAt, groupHasDiff, setAt, unknownRules } from "./profileForm";

const rule = (left: number) => ({ value: { left_mm: left, nest: { a: 1 } }, severity: "error", enabled: true });
const base: Profile = { id: "g", name: "G", base: null, readonly: true, rules: { "page.margins": rule(30), "body.alignment": { value: { align: "justify" }, severity: "error", enabled: true } } };

describe("profileForm", () => {
  it("getAt читает вложенные пути", () => {
    expect(getAt({ a: { b: 2 } }, "a.b")).toBe(2);
    expect(getAt({ a: 1 }, "x.y")).toBeUndefined();
  });
  it("setAt не мутирует", () => {
    const v = { a: { b: 1, c: 2 } };
    const n = setAt(v, "a.b", 5) as typeof v;
    expect(n.a.b).toBe(5);
    expect(n.a.c).toBe(2);
    expect(v.a.b).toBe(1);
    expect(n).not.toBe(v);
  });
  it("differs сравнивает правило целиком", () => {
    expect(differs(rule(30), rule(30))).toBe(false);
    expect(differs(rule(25), rule(30))).toBe(true);
    expect(differs({ ...rule(30), enabled: false }, rule(30))).toBe(true);
    expect(differs(rule(30), undefined)).toBe(false);
  });
  it("groupHasDiff", () => {
    const own: Profile = { ...base, readonly: false, rules: { ...base.rules, "page.margins": rule(25) } };
    expect(groupHasDiff(own, base, "page")).toBe(true);
    expect(groupHasDiff(own, base, "body")).toBe(false);
    expect(groupHasDiff(base, base, "page")).toBe(false);
  });
  it("unknownRules", () => {
    expect(unknownRules({ ...base, rules: { ...base.rules, "x.y": {} } })).toEqual(["x.y"]);
  });
});
