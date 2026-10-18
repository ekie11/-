import { describe, expect, it } from "vitest";
import type { Issue, Report } from "./api";
import { groupIssues, plural, summary } from "./issues";

const i = (rule: string, source = "ГОСТ", message = "m"): Issue => ({ rule, source, message });

describe("groupIssues", () => {
  it("группирует по правилу в порядке первого появления", () => {
    const g = groupIssues([i("b"), i("a"), i("b")]);
    expect(g.map((x) => x.rule)).toEqual(["b", "a"]);
    expect(g[0].items).toHaveLength(2);
    expect(g[0].source).toBe("ГОСТ");
  });
  it("пустой список", () => expect(groupIssues([])).toEqual([]));
});

describe("plural", () => {
  it.each([
    [1, "замечание"],
    [2, "замечания"],
    [5, "замечаний"],
    [11, "замечаний"],
    [21, "замечание"],
    [22, "замечания"],
    [0, "замечаний"],
  ])("%i", (n, w) => expect(plural(n)).toBe(w));
});

const rep = (errors: number, recommendations = 0): Report => ({
  issues: [],
  summary: { errors, recommendations },
});

describe("summary", () => {
  it("check", () => {
    expect(summary(rep(1), "check")).toBe("1 замечание");
    expect(summary(rep(2, 3), "check")).toBe("5 замечаний");
    expect(summary(rep(0), "check")).toBe("Замечаний нет");
  });
  it("format", () => {
    expect(summary(rep(2), "format")).toBe("Оформление готово. Осталось 2 замечания, которые нужно поправить вручную");
    expect(summary(rep(21), "format")).toBe("Оформление готово. Осталось 21 замечание, которое нужно поправить вручную");
    expect(summary(rep(0), "format")).toBe("Оформление готово. Замечаний не осталось");
  });
  it("без summary считает issues", () => {
    expect(summary({ issues: [i("a"), i("b")] }, "check")).toBe("2 замечания");
  });
});
