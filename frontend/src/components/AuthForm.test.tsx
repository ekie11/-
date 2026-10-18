import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(search),
}));
const refresh = vi.fn();
vi.mock("@/lib/useMe", () => ({ useMe: () => ({ me: null, loading: false, refresh }) }));
const apiFetch = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  apiFetch: (...a: unknown[]) => apiFetch(...a),
}));

import { AuthForm } from "./AuthForm";

beforeEach(() => {
  replace.mockReset();
  refresh.mockReset().mockResolvedValue(undefined);
  apiFetch.mockReset();
  search = "";
});

async function fill() {
  await userEvent.type(screen.getByLabelText("Email"), "a@b.c");
  await userEvent.type(screen.getByLabelText("Пароль"), "password1");
}

describe("AuthForm", () => {
  it("показывает detail из 401", async () => {
    apiFetch.mockRejectedValue(new ApiError(401, "Неверный email или пароль"));
    render(<AuthForm mode="login" />);
    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Войти" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Неверный email или пароль");
    expect(replace).not.toHaveBeenCalled();
  });
  it("успешный вход: POST, refresh, переход на next", async () => {
    search = "next=/profiles";
    apiFetch.mockResolvedValue({});
    render(<AuthForm mode="login" />);
    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Войти" }));
    expect(apiFetch).toHaveBeenCalledWith("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "a@b.c", password: "password1" }),
    });
    expect(refresh).toHaveBeenCalled();
    expect(replace).toHaveBeenCalledWith("/profiles");
  });
  it("небезопасный next → /", async () => {
    search = "next=//evil.com";
    apiFetch.mockResolvedValue({});
    render(<AuthForm mode="register" />);
    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Зарегистрироваться" }));
    expect(apiFetch.mock.calls[0][0]).toBe("/auth/register");
    expect(replace).toHaveBeenCalledWith("/");
  });
  it("регистрация: подсказка и ссылка на вход с next", () => {
    search = "next=/profiles";
    render(<AuthForm mode="register" />);
    expect(screen.getByText("Минимум 8 символов")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute("href", "/login?next=%2Fprofiles");
  });
});
