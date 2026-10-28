import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/account",
  useSearchParams: () => new URLSearchParams(""),
}));
const refresh = vi.fn();
const useMe = vi.fn();
vi.mock("@/lib/useMe", () => ({ useMe: () => useMe() }));
const config = vi.fn();
const telegramLink = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const mod = await orig<typeof import("@/lib/api")>();
  return { ...mod, api: { ...mod.api, config: () => config(), telegramLink: (d: unknown) => telegramLink(d) } };
});
let widgetAuth: ((d: Record<string, string | number>) => void) | null = null;
vi.mock("./TelegramLogin", () => ({
  TelegramLogin: ({ botUsername, onAuth }: { botUsername: string | null; onAuth: typeof widgetAuth }) => {
    widgetAuth = onAuth;
    return botUsername ? <div>widget:{botUsername}</div> : null;
  },
}));

import { AccountPage } from "./AccountPage";

const meOf = (over = {}) => ({ id: 1, email: "a@b.c", telegram_name: null, telegram_linked: false, ...over });

beforeEach(() => {
  refresh.mockReset().mockResolvedValue(undefined);
  useMe.mockReset().mockReturnValue({ me: meOf(), loading: false, refresh });
  config.mockReset().mockResolvedValue({ telegram_bot_username: "gost_bot" });
  telegramLink.mockReset();
  widgetAuth = null;
});

describe("AccountPage", () => {
  it("не привязан: показывает email и «Привязать Telegram»", async () => {
    render(<AccountPage />);
    expect(screen.getByText("a@b.c")).toBeInTheDocument();
    expect(await screen.findByText("Привязать Telegram")).toBeInTheDocument();
    expect(screen.getByText("widget:gost_bot")).toBeInTheDocument();
  });
  it("привязан: имя из Telegram, кнопки привязки нет", async () => {
    useMe.mockReturnValue({ me: meOf({ email: null, telegram_name: "Иван", telegram_linked: true }), loading: false, refresh });
    render(<AccountPage />);
    expect(screen.getByText("Иван")).toBeInTheDocument();
    await act(async () => {});
    expect(screen.queryByText("Привязать Telegram")).toBeNull();
  });
  it("без бота в /config кнопки нет", async () => {
    config.mockResolvedValue({ telegram_bot_username: null });
    render(<AccountPage />);
    await act(async () => {});
    expect(screen.queryByText("Привязать Telegram")).toBeNull();
  });
  it("успех привязки: telegramLink и refresh", async () => {
    telegramLink.mockResolvedValue({});
    render(<AccountPage />);
    await screen.findByText("widget:gost_bot");
    await act(async () => widgetAuth!({ id: 5, hash: "h" }));
    expect(telegramLink).toHaveBeenCalledWith({ id: 5, hash: "h" });
    expect(refresh).toHaveBeenCalled();
  });
  it("409 показывает текст ошибки", async () => {
    telegramLink.mockRejectedValue(new ApiError(409, "Этот Telegram уже привязан к другому аккаунту"));
    render(<AccountPage />);
    await screen.findByText("widget:gost_bot");
    await act(async () => widgetAuth!({ id: 5, hash: "h" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Этот Telegram уже привязан к другому аккаунту");
    expect(refresh).not.toHaveBeenCalled();
  });
});
