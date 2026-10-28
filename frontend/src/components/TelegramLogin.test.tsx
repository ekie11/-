import { act, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TelegramLogin } from "./TelegramLogin";

describe("TelegramLogin", () => {
  it("без имени бота ничего не рендерит и не грузит скрипт", () => {
    const { container } = render(<TelegramLogin botUsername={null} onAuth={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
    expect(document.querySelector("script[data-telegram-login]")).toBeNull();
  });
  it("вставляет скрипт виджета и вызывает onAuth из глобального callback", () => {
    const onAuth = vi.fn();
    const { unmount } = render(<TelegramLogin botUsername="gost_bot" onAuth={onAuth} />);
    const script = document.querySelector("script[data-telegram-login]")!;
    expect(script.getAttribute("src")).toBe("https://telegram.org/js/telegram-widget.js?22");
    expect(script.getAttribute("data-telegram-login")).toBe("gost_bot");
    expect(script.getAttribute("data-size")).toBe("large");
    const call = script.getAttribute("data-onauth")!;
    const name = call.replace("(user)", "");
    expect(call).toMatch(/^onTelegramAuth_\w+\(user\)$/);
    const user = { id: 1, hash: "h" };
    act(() => (window[name] as (u: unknown) => void)(user));
    expect(onAuth).toHaveBeenCalledWith(user);
    unmount();
    expect(window[name]).toBeUndefined();
    expect(document.querySelector("script[data-telegram-login]")).toBeNull();
  });
});
