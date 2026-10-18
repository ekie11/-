import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
const useMe = vi.fn();
vi.mock("@/lib/useMe", () => ({ useMe: () => useMe() }));
const apiFetch = vi.fn();
vi.mock("@/lib/api", () => ({ apiFetch: (...a: unknown[]) => apiFetch(...a) }));

import { Header } from "./Header";

beforeEach(() => {
  push.mockReset();
  apiFetch.mockReset();
});

describe("Header", () => {
  it("гость: ссылка «Войти», нет «Мои профили»", () => {
    useMe.mockReturnValue({ me: null, loading: false, refresh: vi.fn() });
    render(<Header />);
    expect(screen.getByText("ГОСТ-сервис")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Войти" })).toBeInTheDocument();
    expect(screen.queryByText("Мои профили")).toBeNull();
    expect(screen.getByRole("link", { name: "Мои документы" })).toHaveAttribute("href", "/documents");
  });
  it("пользователь: email и «Выйти» вызывает logout, refresh и переход на /", async () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    useMe.mockReturnValue({ me: { id: 1, email: "a@b.c" }, loading: false, refresh });
    apiFetch.mockResolvedValue(undefined);
    render(<Header />);
    expect(screen.getByText("a@b.c")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Мои профили" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Выйти" }));
    expect(apiFetch).toHaveBeenCalledWith("/auth/logout", { method: "POST" });
    expect(refresh).toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/");
  });
  it("ошибка logout не ломает выход", async () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    useMe.mockReturnValue({ me: { id: 1, email: "a@b.c" }, loading: false, refresh });
    apiFetch.mockRejectedValue(new Error("down"));
    render(<Header />);
    await userEvent.click(screen.getByRole("button", { name: "Выйти" }));
    expect(refresh).toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/");
  });
});
