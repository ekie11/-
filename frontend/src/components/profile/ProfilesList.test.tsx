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
let enabled = true;
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
  enabled = true;
  apiFetch.mockReset().mockImplementation(async (p: string, init?: RequestInit) =>
    p === "/profile-fields"
      ? { groups: [], rule_labels: {}, fields: [], extraction_enabled: enabled }
      : init?.method === "POST"
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
  it("кнопка «Создать из методички» — только если функция включена", async () => {
    render(<ProfilesList />);
    expect(await screen.findByRole("link", { name: "Создать из методички" })).toHaveAttribute("href", "/profiles/from-guideline");
  });
  it("кнопка скрыта при extraction_enabled=false", async () => {
    enabled = false;
    render(<ProfilesList />);
    await screen.findByRole("link", { name: "Мой" });
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith("/profile-fields"));
    expect(screen.queryByRole("link", { name: "Создать из методички" })).toBeNull();
  });
});
