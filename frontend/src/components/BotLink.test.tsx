import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const config = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const mod = await orig<typeof import("@/lib/api")>();
  return { ...mod, api: { ...mod.api, config: () => config() } };
});

import { BotLink } from "./BotLink";

describe("BotLink", () => {
  it("ссылка на бота, если задан username", async () => {
    config.mockResolvedValue({ telegram_bot_username: "gost_bot" });
    render(<BotLink />);
    expect(await screen.findByRole("link", { name: "@gost_bot" })).toHaveAttribute("href", "https://t.me/gost_bot");
  });
  it("без username ничего нет", async () => {
    config.mockResolvedValue({ telegram_bot_username: null });
    const { container } = render(<BotLink />);
    await Promise.resolve();
    expect(container).toBeEmptyDOMElement();
  });
});
