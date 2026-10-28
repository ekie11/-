import { act, render, screen } from "@testing-library/react";
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
const config = vi.fn();
const telegramLogin = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const mod = await orig<typeof import("@/lib/api")>();
  return {
    ...mod,
    apiFetch: (...a: unknown[]) => apiFetch(...a),
    api: { ...mod.api, config: () => config(), telegramLogin: (d: unknown) => telegramLogin(d) },
  };
});
let widgetAuth: ((d: Record<string, string | number>) => void) | null = null;
vi.mock("./TelegramLogin", () => ({
  TelegramLogin: ({ botUsername, onAuth }: { botUsername: string | null; onAuth: typeof widgetAuth }) => {
    widgetAuth = onAuth;
    return botUsername ? <div>widget:{botUsername}</div> : null;
  },
}));

import { AuthForm } from "./AuthForm";

beforeEach(() => {
  replace.mockReset();
  refresh.mockReset().mockResolvedValue(undefined);
  apiFetch.mockReset();
  config.mockReset().mockResolvedValue({ telegram_bot_username: null });
  telegramLogin.mockReset();
  widgetAuth = null;
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
  it("без telegram_bot_username кнопки Telegram нет", async () => {
    render(<AuthForm mode="login" />);
    await Promise.resolve();
    expect(screen.queryByText(/widget:/)).toBeNull();
  });
  it("виджет: telegramLogin, refresh и переход на next", async () => {
    search = "next=/profiles";
    config.mockResolvedValue({ telegram_bot_username: "gost_bot" });
    telegramLogin.mockResolvedValue({});
    render(<AuthForm mode="login" />);
    expect(await screen.findByText("widget:gost_bot")).toBeInTheDocument();
    await act(async () => widgetAuth!({ id: 1, hash: "h" }));
    expect(telegramLogin).toHaveBeenCalledWith({ id: 1, hash: "h" });
    expect(refresh).toHaveBeenCalled();
    expect(replace).toHaveBeenCalledWith("/profiles");
  });
  it("виджет: ошибка API показывается, перехода нет", async () => {
    config.mockResolvedValue({ telegram_bot_username: "gost_bot" });
    telegramLogin.mockRejectedValue(new ApiError(401, "Не удалось подтвердить вход через Telegram"));
    render(<AuthForm mode="login" />);
    await screen.findByText("widget:gost_bot");
    await act(async () => widgetAuth!({ id: 1, hash: "bad" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось подтвердить вход через Telegram");
    expect(replace).not.toHaveBeenCalled();
  });
});
