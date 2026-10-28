import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";

const push = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(search),
}));
let me: { id: number; email: string | null; telegram_name: string | null; telegram_linked: boolean } | null = null;
vi.mock("@/lib/useMe", () => ({ useMe: () => ({ me, loading: false, refresh: vi.fn() }) }));
const apiFetch = vi.fn();
const apiUpload = vi.fn();
vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/api")>()),
  apiFetch: (...a: unknown[]) => apiFetch(...a),
  apiUpload: (...a: unknown[]) => apiUpload(...a),
}));

import { Wizard } from "./Wizard";

const PROFILES = [
  { id: "gost", name: "ГОСТ 7.32-2017", base: null, readonly: true },
  { id: "own", name: "Мой", base: "gost", readonly: false },
];

beforeEach(() => {
  push.mockReset();
  apiFetch.mockReset().mockResolvedValue(PROFILES);
  apiUpload.mockReset();
  search = "";
  me = null;
});

async function toStep2() {
  const view = render(<Wizard />);
  await userEvent.click(screen.getByRole("tab", { name: "Вставить текст" }));
  await userEvent.type(screen.getByLabelText("Текст документа"), "Привет");
  await userEvent.click(screen.getByRole("button", { name: "Далее" }));
  expect(push).toHaveBeenCalledWith(expect.stringContaining("step=2"));
  search = search ? `${search}&step=2` : "step=2";
  view.rerender(<Wizard />);
  return view;
}

describe("Wizard", () => {
  it("«Далее» неактивна без ввода", () => {
    render(<Wizard />);
    expect(screen.getByRole("button", { name: "Далее" })).toBeDisabled();
  });

  it("step=2 без ввода показывает шаг 1", () => {
    search = "step=2";
    render(<Wizard />);
    expect(screen.getByRole("button", { name: "Далее" })).toBeInTheDocument();
  });

  it("неверный файл показывает ошибку и не открывает «Далее»", async () => {
    render(<Wizard />);
    await userEvent.upload(screen.getByLabelText("Выбрать файл .docx"), new File(["x"], "a.pdf"), { applyAccept: false });
    expect(screen.getByRole("alert")).toHaveTextContent("Нужен файл .docx");
    expect(screen.getByRole("button", { name: "Далее" })).toBeDisabled();
  });

  it("текст ведёт на шаг 2; гостю «Свои требования — после регистрации»", async () => {
    await toStep2();
    expect(await screen.findByRole("button", { name: "Запустить" })).toBeInTheDocument();
    expect(screen.getByText("Свои требования — после регистрации")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Требования")).toHaveValue("gost"));
  });

  it("вошедшему ссылка «Настроить свои требования»", async () => {
    me = { id: 1, email: "a@b.c", telegram_name: null, telegram_linked: false };
    await toStep2();
    expect(await screen.findByRole("link", { name: "Настроить свои требования" })).toHaveAttribute(
      "href",
      "/profiles?return=wizard",
    );
  });

  it("?profile= выбирает профиль", async () => {
    search = "profile=own";
    await toStep2();
    await waitFor(() => expect(screen.getByLabelText("Требования")).toHaveValue("own"));
  });

  it("двойной клик «Запустить» шлёт один запрос", async () => {
    let resolve!: (v: { id: number }) => void;
    apiUpload.mockReturnValue(new Promise((r) => (resolve = r)));
    await toStep2();
    const btn = await screen.findByRole("button", { name: "Запустить" });
    await waitFor(() => expect(screen.getByLabelText("Требования")).toHaveValue("gost"));
    await userEvent.dblClick(btn);
    expect(apiUpload).toHaveBeenCalledTimes(1);
    const form = apiUpload.mock.calls[0][1] as FormData;
    expect(form.get("profile_id")).toBe("gost");
    expect(form.get("mode")).toBe("format");
    expect(form.get("text")).toBe("Привет");
    resolve({ id: 5 });
    await waitFor(() => expect(push).toHaveBeenCalledWith("/jobs/5"));
  });

  it("429 показывает текст и ссылку «Зарегистрироваться»", async () => {
    apiUpload.mockRejectedValue(new ApiError(429, "Зарегистрируйтесь, чтобы продолжить"));
    await toStep2();
    await waitFor(() => expect(screen.getByLabelText("Требования")).toHaveValue("gost"));
    await userEvent.click(await screen.findByRole("button", { name: "Запустить" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Зарегистрируйтесь, чтобы продолжить");
    expect(screen.getByRole("link", { name: "Зарегистрироваться" })).toHaveAttribute("href", "/register?next=/");
    expect(screen.getByRole("button", { name: "Запустить" })).toBeEnabled();
  });

  it("для вставленного текста «Оформить» выбрано, «Проверить» недоступно, в запрос уходит format", async () => {
    apiUpload.mockResolvedValue({ id: 5 });
    await toStep2();
    expect(await screen.findByRole("button", { name: "Запустить" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Проверить/ })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /Оформить/ })).toBeChecked();
    expect(
      screen.getByText("Для вставленного текста доступно только оформление: у него ещё нет своего форматирования"),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Требования")).toHaveValue("gost"));
    await userEvent.click(screen.getByRole("button", { name: "Запустить" }));
    const form = apiUpload.mock.calls[0][1] as FormData;
    expect(form.get("mode")).toBe("format");
  });

  it("для файла «Проверить» доступно и выбрано по умолчанию", async () => {
    search = "step=2";
    const view = render(<Wizard />);
    await userEvent.upload(screen.getByLabelText("Выбрать файл .docx"), new File(["x"], "a.docx"), { applyAccept: false });
    view.rerender(<Wizard />);
    expect(await screen.findByRole("radio", { name: /Проверить/ })).toBeEnabled();
    expect(screen.getByRole("radio", { name: /Проверить/ })).toBeChecked();
    expect(screen.queryByText(/доступно только оформление/)).toBeNull();
  });
});
