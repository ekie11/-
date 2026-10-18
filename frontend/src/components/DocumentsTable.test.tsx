import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  apiFetch: (...a: unknown[]) => apiFetch(...a),
}));

import { DocumentsTable } from "./DocumentsTable";

beforeEach(() => {
  apiFetch.mockReset();
});

describe("DocumentsTable", () => {
  it("показывает строки со ссылками на задачи и подписями", async () => {
    apiFetch.mockResolvedValue([
      {
        id: 7,
        status: "done",
        mode: "check",
        profile_name: "Мой профиль",
        created_at: "2026-10-18T11:05:00Z",
        expires_at: "2026-10-19T11:05:00Z",
      },
    ]);
    render(<DocumentsTable />);
    const link = await screen.findByRole("link", { name: "18 окт. 2026 г., 14:05" });
    expect(link).toHaveAttribute("href", "/jobs/7");
    expect(apiFetch).toHaveBeenCalledWith("/jobs");
    expect(screen.getByRole("columnheader", { name: "Дата" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Профиль" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Режим" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Статус" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Хранится до" })).toBeInTheDocument();
    expect(screen.getByText("Проверка")).toBeInTheDocument();
    expect(screen.getByText("Готово")).toBeInTheDocument();
    expect(screen.getByText("19 окт. 2026 г., 14:05")).toBeInTheDocument();
  });

  it("пустое состояние со ссылкой на мастер", async () => {
    apiFetch.mockResolvedValue([]);
    render(<DocumentsTable />);
    expect(await screen.findByText("Пока нет документов")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /мастер/i })).toHaveAttribute("href", "/");
  });

  it("показывает загрузку, затем ошибку API", async () => {
    apiFetch.mockRejectedValue(new Error("boom"));
    render(<DocumentsTable />);
    expect(screen.getByText("Загружаем…")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Не удалось загрузить документы"));
  });
});
