import { describe, expect, it } from "vitest";
import { format } from "./format";

describe("format.statusLabel", () => {
  it.each([
    ["queued", "В очереди"],
    ["running", "Обрабатывается"],
    ["done", "Готово"],
    ["error", "Ошибка"],
    ["expired", "Срок хранения истёк"],
  ] as const)("%s → %s", (status, label) => {
    expect(format.statusLabel(status)).toBe(label);
  });
});

describe("format.modeLabel", () => {
  it.each([
    ["check", "Проверка"],
    ["format", "Оформление"],
  ] as const)("%s → %s", (mode, label) => {
    expect(format.modeLabel(mode)).toBe(label);
  });
});

describe("format.dateTime", () => {
  it("форматирует время в московском часовом поясе", () => {
    // 11:05 UTC = 14:05 MSK
    expect(format.dateTime("2026-10-18T11:05:00Z")).toBe("18 окт. 2026 г., 14:05");
  });
});
