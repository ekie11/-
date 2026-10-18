import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(search),
}));
const apiFetch = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  apiFetch: (...a: unknown[]) => apiFetch(...a),
}));

import { ProfileEditor } from "./ProfileEditor";

const R = (v: unknown, extra = {}) => ({ value: v, severity: "error", enabled: true, source: "п. 6.1.1", ...extra });
const GOST = {
  id: "gost", name: "ГОСТ 7.32-2017", base: null, readonly: true,
  rules: {
    "page.margins": R({ top_mm: 20, bottom_mm: 20, left_mm: 30, right_mm: 15 }),
    "body.alignment": R({ align: "justify" }),
  },
};
const OWN = {
  id: "own", name: "Мой", base: "gost", readonly: false,
  rules: { ...GOST.rules, "custom.thing": { value: { z: [1, 2] }, severity: "error", enabled: true } },
  diff: {},
};

beforeEach(() => {
  push.mockReset();
  search = "";
  apiFetch.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "PUT") return JSON.parse(init.body as string);
    if (path === "/profiles/own") return structuredClone(OWN);
    if (path === "/profiles/gost") return structuredClone(GOST);
    throw new Error(path);
  });
});

describe("ProfileEditor", () => {
  it("изменение поля подсвечивает строку и группу, возврат снимает", async () => {
    render(<ProfileEditor id="own" />);
    const left = await screen.findByLabelText("Левое поле");
    const row = left.closest("[data-differs]")!;
    expect(row).toHaveAttribute("data-differs", "false");
    await userEvent.clear(left);
    await userEvent.type(left, "25");
    expect(row).toHaveAttribute("data-differs", "true");
    expect(screen.getByRole("button", { name: /Страница/ })).toHaveAttribute("data-diff", "true");
    await userEvent.click(screen.getByRole("button", { name: "вернуть как в ГОСТе" }));
    expect(row).toHaveAttribute("data-differs", "false");
    expect(screen.getByRole("button", { name: /Страница/ })).toHaveAttribute("data-diff", "false");
    expect((screen.getByLabelText("Левое поле") as HTMLInputElement).value).toBe("30");
  });

  it("«Сохранить» шлёт PUT с изменённым значением; неописанное правило не меняется", async () => {
    render(<ProfileEditor id="own" />);
    const left = await screen.findByLabelText("Левое поле");
    await userEvent.clear(left);
    await userEvent.type(left, "25");
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith("/profiles/own", expect.objectContaining({ method: "PUT" })));
    const call = apiFetch.mock.calls.find((c) => c[1]?.method === "PUT")!;
    const body = JSON.parse(call[1].body);
    expect(body.rules["page.margins"].value.left_mm).toBe(25);
    expect(body.rules["custom.thing"]).toEqual(OWN.rules["custom.thing"]);
    expect(body.name).toBe("Мой");
  });

  it("число вне пределов приводится к ним при уходе из поля", async () => {
    render(<ProfileEditor id="own" />);
    const left = await screen.findByLabelText("Левое поле");
    await userEvent.clear(left);
    await userEvent.type(left, "99");
    await userEvent.tab();
    expect((screen.getByLabelText("Левое поле") as HTMLInputElement).value).toBe("50");
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(apiFetch.mock.calls.some((c) => c[1]?.method === "PUT")).toBe(true));
    const body = JSON.parse(apiFetch.mock.calls.find((c) => c[1]?.method === "PUT")![1].body);
    expect(body.rules["page.margins"].value.left_mm).toBe(50);
  });

  it("число ниже минимума поднимается до него", async () => {
    render(<ProfileEditor id="own" />);
    const left = await screen.findByLabelText("Левое поле");
    await userEvent.clear(left);
    await userEvent.type(left, "-5");
    await userEvent.tab();
    expect((screen.getByLabelText("Левое поле") as HTMLInputElement).value).toBe("0");
  });

  it("фиксированное поле без значения показывает вариант по умолчанию без предупреждения", async () => {
    apiFetch.mockImplementation(async (path: string) => {
      if (path === "/profiles/own") {
        const p = structuredClone(OWN) as typeof OWN & { rules: Record<string, unknown> };
        p.rules["captions.figure"] = R({ pattern: "Рисунок {n} — {title}", align: "center" });
        return p;
      }
      return structuredClone(GOST);
    });
    render(<ProfileEditor id="own" />);
    await userEvent.click(await screen.findByRole("button", { name: /Рисунки и таблицы/ }));
    expect(screen.getByText("под рисунком", { selector: "[data-fixed]" })).toBeInTheDocument();
    expect(screen.queryByText(/Это значение не поддерживается/)).toBeNull();
  });

  it("неподдерживаемое сохранённое значение не скрывается", async () => {
    apiFetch.mockImplementation(async (path: string) => {
      if (path === "/profiles/own") {
        const p = structuredClone(OWN) as typeof OWN & { rules: Record<string, unknown> };
        p.rules["captions.figure"] = R({ pattern: "Рисунок {n} — {title}", position: "above", align: "center" });
        return p;
      }
      return structuredClone(GOST);
    });
    render(<ProfileEditor id="own" />);
    await userEvent.click(await screen.findByRole("button", { name: /Рисунки и таблицы/ }));
    expect(screen.getByText("above")).toBeInTheDocument();
    expect(screen.getByText(/Это значение не поддерживается — будет использовано: под рисунком/)).toBeInTheDocument();
  });

  it("правило без описания показывается в «Другом»", async () => {
    render(<ProfileEditor id="own" />);
    await userEvent.click(await screen.findByRole("button", { name: /Другое/ }));
    expect(screen.getByText("custom.thing")).toBeInTheDocument();
    expect(screen.getByText(/"z"/)).toBeInTheDocument();
  });

  it("?return=wizard после сохранения ведёт в мастер", async () => {
    search = "return=wizard";
    render(<ProfileEditor id="own" />);
    await screen.findByLabelText("Левое поле");
    await userEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/?profile=own"));
  });

  it("ГОСТ-профиль: поля отключены, есть «Создать свой на основе»", async () => {
    render(<ProfileEditor id="gost" />);
    expect(await screen.findByLabelText("Левое поле")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Создать свой на основе" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Сохранить" })).toBeNull();
  });

  it("удаление спрашивает подтверждение", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ProfileEditor id="own" />);
    await screen.findByLabelText("Левое поле");
    await userEvent.click(screen.getByRole("button", { name: "Удалить" }));
    expect(confirm).toHaveBeenCalledWith("Удалить профиль?");
    await waitFor(() => expect(push).toHaveBeenCalledWith("/profiles"));
    confirm.mockRestore();
  });
});
