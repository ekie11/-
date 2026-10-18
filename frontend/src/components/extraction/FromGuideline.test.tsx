import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
const apiFetch = vi.fn();
const api = {
  createExtraction: vi.fn(),
  getExtraction: vi.fn(),
  getQuota: vi.fn(),
  createProfileFromExtraction: vi.fn(),
};
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  apiFetch: (...a: unknown[]) => apiFetch(...a),
  api: {
    createExtraction: (...a: unknown[]) => api.createExtraction(...a),
    getExtraction: (...a: unknown[]) => api.getExtraction(...a),
    getQuota: (...a: unknown[]) => api.getQuota(...a),
    createProfileFromExtraction: (...a: unknown[]) => api.createProfileFromExtraction(...a),
  },
}));

import { ApiError } from "@/lib/api";
import { FromGuideline, POLL_MS } from "./FromGuideline";

const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
const running = { id: "x", status: "running", base_profile_id: "g", source_name: null, result: null, error: null };
const done = {
  ...running,
  status: "done",
  result: { found: [{ rule: "page.margins", path: "left_mm", value: 25, quote: "q", page: 1 }], unsupported: [], rejected_count: 0 },
};

beforeEach(() => {
  vi.useFakeTimers();
  push.mockReset();
  Object.values(api).forEach((m) => m.mockReset());
  api.getQuota.mockResolvedValue({ used: 1, limit: 5 });
  api.createExtraction.mockResolvedValue({ id: "x" });
  apiFetch.mockReset().mockImplementation(async (p: string) => {
    if (p === "/profile-fields")
      return {
        groups: [{ id: "page", label: "Страница" }],
        rule_labels: {},
        fields: [{ rule: "page.margins", path: "left_mm", group: "page", label: "Левое поле", kind: "number", unit: "мм" }],
        extraction_enabled: true,
      };
    if (p === "/profiles") return [{ id: "g", name: "ГОСТ", base: null, readonly: true }];
    return { id: "g", name: "ГОСТ", base: null, readonly: true, rules: { "page.margins": { value: { left_mm: 30 } } } };
  });
});
afterEach(() => vi.useRealTimers());

async function submitText() {
  render(<FromGuideline />);
  await flush();
  fireEvent.click(screen.getByRole("tab", { name: "Вставить текст" }));
  fireEvent.change(screen.getByLabelText("Текст методички"), { target: { value: "Поля 25 мм" } });
  fireEvent.click(screen.getByRole("button", { name: "Извлечь требования" }));
  await flush();
}

describe("FromGuideline", () => {
  it("опрашивает раз в 2 с до готовности, затем таблица", async () => {
    api.getExtraction.mockResolvedValueOnce(running).mockResolvedValueOnce(running).mockResolvedValue(done);
    await submitText();
    expect(screen.getByText("Читаем методичку… обычно до минуты")).toBeInTheDocument();
    expect(api.getExtraction).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS); });
    expect(api.getExtraction).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS); });
    expect(api.getExtraction).toHaveBeenCalledTimes(3);
    await flush();
    expect(screen.getByText("Левое поле")).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS * 3); });
    expect(api.getExtraction).toHaveBeenCalledTimes(3);
  });

  it("failed: текст API и «Попробовать снова»", async () => {
    api.getExtraction.mockResolvedValue({ ...running, status: "failed", error: "Модель недоступна" });
    await submitText();
    expect(screen.getByText("Модель недоступна")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Попробовать снова" }));
    expect(screen.getByRole("button", { name: "Извлечь требования" })).toBeInTheDocument();
  });

  it("опрос останавливается при размонтировании", async () => {
    api.getExtraction.mockResolvedValue(running);
    const { unmount } = render(<FromGuideline />);
    await flush();
    fireEvent.click(screen.getByRole("tab", { name: "Вставить текст" }));
    fireEvent.change(screen.getByLabelText("Текст методички"), { target: { value: "т" } });
    fireEvent.click(screen.getByRole("button", { name: "Извлечь требования" }));
    await flush();
    expect(api.getExtraction).toHaveBeenCalledTimes(1);
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS * 5); });
    expect(api.getExtraction).toHaveBeenCalledTimes(1);
  });

  it("отклоняет файл >20 МБ и не DOCX/PDF", async () => {
    render(<FromGuideline />);
    await flush();
    const input = document.getElementById("docx-file") as HTMLInputElement;
    const big = new File(["x"], "m.docx");
    Object.defineProperty(big, "size", { value: 21 * 1024 * 1024 });
    fireEvent.change(input, { target: { files: [big] } });
    expect(screen.getByText("Файл больше 20 МБ")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Извлечь требования" })).toBeDisabled();
    fireEvent.change(input, { target: { files: [new File(["x"], "m.txt")] } });
    expect(screen.getByText("Нужен файл DOCX или PDF")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Извлечь требования" })).toBeDisabled();
  });

  it("кнопка отключена, когда лимит исчерпан", async () => {
    api.getQuota.mockResolvedValue({ used: 5, limit: 5 });
    render(<FromGuideline />);
    await flush();
    fireEvent.click(screen.getByRole("tab", { name: "Вставить текст" }));
    fireEvent.change(screen.getByLabelText("Текст методички"), { target: { value: "т" } });
    expect(screen.getByText("Осталось 0 из 5 на сегодня")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Извлечь требования" })).toBeDisabled();
  });

  it("после 5 сетевых сбоев подряд опрос прекращается с ошибкой", async () => {
    api.getExtraction.mockRejectedValue(new ApiError(0, "Сервер недоступен, попробуйте позже"));
    await submitText();
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_MS * 10); });
    expect(api.getExtraction).toHaveBeenCalledTimes(5);
    expect(screen.getByText("Сервер недоступен, попробуйте позже")).toBeInTheDocument();
  });
});
