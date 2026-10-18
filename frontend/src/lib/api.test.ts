import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch, apiUpload } from "./api";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(impl: () => Promise<Response>) {
  const f = vi.fn<(url: string, init: RequestInit) => Promise<Response>>(impl);
  vi.stubGlobal("fetch", f);
  return f;
}

describe("apiFetch", () => {
  it("возвращает JSON при 200 и ходит на /api с cookie", async () => {
    const f = stubFetch(async () => new Response(JSON.stringify({ id: 1, email: "a@b.c" }), { status: 200 }));
    const me = await apiFetch<{ id: number }>("/auth/me");
    expect(me.id).toBe(1);
    const [url, init] = f.mock.calls[0];
    expect(url).toBe("/api/auth/me");
    expect(init.credentials).toBe("include");
  });

  it("бросает ApiError с detail при 400", async () => {
    stubFetch(async () => new Response(JSON.stringify({ detail: "Неверные данные запроса" }), { status: 400 }));
    const err = (await apiFetch("/x").catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.detail).toBe("Неверные данные запроса");
  });

  it("сетевая ошибка даёт русское сообщение", async () => {
    stubFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    const err = (await apiFetch("/x").catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.detail).toBe("Сервер недоступен, попробуйте позже");
  });

  it("не-JSON ошибка даёт русское сообщение", async () => {
    stubFetch(async () => new Response("<html>", { status: 502 }));
    const err = (await apiFetch("/x").catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(502);
    expect(err.detail).toBe("Сервер недоступен, попробуйте позже");
  });

  it("204 возвращает undefined", async () => {
    stubFetch(async () => new Response(null, { status: 204 }));
    expect(await apiFetch("/auth/logout", { method: "POST" })).toBeUndefined();
  });

  it("отправляет JSON-тело с Content-Type", async () => {
    const f = stubFetch(async () => new Response("{}", { status: 200 }));
    await apiFetch("/auth/login", { method: "POST", body: JSON.stringify({ a: 1 }) });
    const init = f.mock.calls[0][1];
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });
});

describe("apiUpload", () => {
  it("шлёт FormData без Content-Type", async () => {
    const f = stubFetch(async () => new Response(JSON.stringify({ id: 5, status: "queued" }), { status: 202 }));
    const form = new FormData();
    form.append("mode", "check");
    const r = await apiUpload<{ id: number }>("/jobs", form);
    expect(r.id).toBe(5);
    const init = f.mock.calls[0][1];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(form);
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });
});
