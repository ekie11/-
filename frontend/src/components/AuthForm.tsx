"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, ApiError, apiFetch, type TelegramAuthData } from "@/lib/api";
import { safeNext } from "@/lib/nav";
import { useBotUsername } from "@/lib/useBotUsername";
import { useMe } from "@/lib/useMe";
import { TelegramLogin } from "./TelegramLogin";
import { Button } from "./ui/Button";
import { ErrorBanner } from "./ui/ErrorBanner";
import { TextField } from "./ui/TextField";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useMe();
  const botUsername = useBotUsername();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const next = params.get("next");
  const isLogin = mode === "login";
  const otherHref = `${isLogin ? "/register" : "/login"}${next ? `?next=${encodeURIComponent(next)}` : ""}`;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/auth/${mode}`, { method: "POST", body: JSON.stringify({ email, password }) });
      await refresh();
      router.replace(safeNext(next));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось выполнить запрос");
      setBusy(false);
    }
  }

  async function telegramAuth(data: TelegramAuthData) {
    setError(null);
    try {
      await api.telegramLogin(data);
      await refresh();
      router.replace(safeNext(next));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось выполнить запрос");
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-4 text-2xl font-semibold">{isLogin ? "Вход" : "Регистрация"}</h1>
      <form onSubmit={submit} className="flex flex-col gap-4">
        {error && <ErrorBanner message={error} />}
        <TextField label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <div className="flex flex-col gap-1">
          <TextField
            label="Пароль"
            type="password"
            autoComplete={isLogin ? "current-password" : "new-password"}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {!isLogin && <p className="text-sm text-muted">Минимум 8 символов</p>}
        </div>
        <Button type="submit" variant="primary" loading={busy}>{isLogin ? "Войти" : "Зарегистрироваться"}</Button>
      </form>
      {botUsername && (
        <div className="mt-4 flex flex-col items-start gap-2">
          <p className="text-sm text-muted">или</p>
          <TelegramLogin botUsername={botUsername} onAuth={telegramAuth} />
        </div>
      )}
      <p className="mt-4 text-sm text-muted">
        {isLogin ? "Нет аккаунта? " : "Уже есть аккаунт? "}
        <Link href={otherHref} className="text-accent underline underline-offset-2">{isLogin ? "Зарегистрироваться" : "Войти"}</Link>
      </p>
    </div>
  );
}
