import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, type Job } from "@/lib/api";

let me: { id: number; email: string } | null = null;
vi.mock("@/lib/useMe", () => ({ useMe: () => ({ me, loading: false, refresh: vi.fn() }) }));
const apiFetch = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  apiFetch: (...a: unknown[]) => apiFetch(...a),
}));

import { JobResult } from "./JobResult";

const job = (over: Partial<Job>): Job => ({
  id: 7, status: "done", mode: "format", error: null, report: null,
  has_pdf: true, created_at: "", expires_at: null, ...over,
});

beforeEach(() => {
  vi.useFakeTimers();
  apiFetch.mockReset();
  me = null;
});
afterEach(() => vi.useRealTimers());

async function flush() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

describe("JobResult", () => {
  it("running опрашивает каждые 2 с, пока не done, и затем останавливается", async () => {
    apiFetch
      .mockResolvedValueOnce(job({ status: "running" }))
      .mockResolvedValueOnce(job({ status: "running" }))
      .mockResolvedValue(job({ report: { issues: [], summary: { errors: 0, recommendations: 0 } } }));
    render(<JobResult id="7" />);
    await flush();
    expect(screen.getByText("Обрабатываем…")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
    expect(apiFetch).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(apiFetch).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(apiFetch).toHaveBeenCalledTimes(3);
    expect(screen.getByText("Оформление готово. Замечаний не осталось")).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(apiFetch).toHaveBeenCalledTimes(3);
  });

  it("done: сводка, ссылки, iframe, плашка гостя", async () => {
    apiFetch.mockResolvedValue(
      job({
        mode: "check",
        report: {
          issues: [{ rule: "body.font_size", source: "ГОСТ 7.32 п. 6.1", message: "Шрифт мал" }],
          summary: { errors: 1, recommendations: 0 },
        },
      }),
    );
    render(<JobResult id="7" />);
    await flush();
    expect(screen.getByText("1 замечание")).toBeInTheDocument();
    expect(screen.getByText("Шрифт мал")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Скачать DOCX" })).toHaveAttribute("href", "/api/jobs/7/docx");
    expect(screen.getByRole("link", { name: "Скачать PDF" })).toHaveAttribute("href", "/api/jobs/7/pdf");
    expect(screen.getByTitle("Предпросмотр PDF")).toHaveAttribute("src", "/api/jobs/7/pdf");
    expect(screen.getByText(/Результат хранится 24 часа/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Зарегистрироваться" })).toHaveAttribute("href", "/register?next=/jobs/7");
  });

  it("зарегистрированному плашка не нужна; без PDF нет iframe", async () => {
    me = { id: 1, email: "a@b.c" };
    apiFetch.mockResolvedValue(job({ has_pdf: false, report: { issues: [] } }));
    render(<JobResult id="7" />);
    await flush();
    expect(screen.queryByText(/Результат хранится 24 часа/)).toBeNull();
    expect(screen.queryByTitle("Предпросмотр PDF")).toBeNull();
    expect(screen.queryByRole("link", { name: "Скачать PDF" })).toBeNull();
  });

  it("error: текст и «Попробовать снова»", async () => {
    apiFetch.mockResolvedValue(job({ status: "error", error: "Файл повреждён" }));
    render(<JobResult id="7" />);
    await flush();
    expect(screen.getByRole("alert")).toHaveTextContent("Файл повреждён");
    expect(screen.getByRole("link", { name: "Попробовать снова" })).toHaveAttribute("href", "/");
  });

  it("404 показывает detail и не опрашивает дальше", async () => {
    apiFetch.mockRejectedValue(new ApiError(404, "Задача не найдена"));
    render(<JobResult id="7" />);
    await flush();
    expect(screen.getByRole("alert")).toHaveTextContent("Задача не найдена");
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });

  it("остановка опроса при размонтировании", async () => {
    apiFetch.mockResolvedValue(job({ status: "queued" }));
    const { unmount } = render(<JobResult id="7" />);
    await flush();
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });
});
