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
const apiUpload = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  apiFetch: (...a: unknown[]) => apiFetch(...a),
  apiUpload: (...a: unknown[]) => apiUpload(...a),
}));

import { ProfilesList } from "./ProfilesList";

beforeEach(() => {
  push.mockReset();
  search = "return=wizard";
  apiUpload.mockReset().mockResolvedValue({ id: "imp" });
  apiFetch.mockReset().mockImplementation(async (_p: string, init?: RequestInit) =>
    init?.method === "POST"
      ? { id: "new" }
      : [
          { id: "gost", name: "ГОСТ 7.32-2017", base: null, readonly: true },
          { id: "own", name: "Мой", base: "gost", readonly: false },
        ],
  );
});

describe("ProfilesList", () => {
  it("показывает только свои профили, сохраняя return", async () => {
    render(<ProfilesList />);
    const link = await screen.findByRole("link", { name: "Мой" });
    expect(link).toHaveAttribute("href", "/profiles/own?return=wizard");
  });
  it("создание на основе ГОСТа", async () => {
    render(<ProfilesList />);
    await screen.findByRole("link", { name: "Мой" });
    await userEvent.click(screen.getByRole("button", { name: "Создать на основе ГОСТа" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/profiles/new?return=wizard"));
    const post = apiFetch.mock.calls.find((c) => c[1]?.method === "POST")!;
    expect(JSON.parse(post[1].body)).toEqual({ base_id: "gost", name: "Мой профиль" });
  });
  it("импорт", async () => {
    render(<ProfilesList />);
    await screen.findByRole("link", { name: "Мой" });
    await userEvent.upload(screen.getByLabelText("Файл профиля (JSON)"), new File(["{}"], "p.json", { type: "application/json" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/profiles/imp?return=wizard"));
  });
});
