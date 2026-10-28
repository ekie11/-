"use client";

import { useState } from "react";
import { api, ApiError, type TelegramAuthData } from "@/lib/api";
import { useBotUsername } from "@/lib/useBotUsername";
import { useMe } from "@/lib/useMe";
import { RequireAuth } from "./RequireAuth";
import { TelegramLogin } from "./TelegramLogin";
import { ErrorBanner } from "./ui/ErrorBanner";

function Account() {
  const { me, refresh } = useMe();
  const botUsername = useBotUsername();
  const [error, setError] = useState<string | null>(null);

  async function link(data: TelegramAuthData) {
    setError(null);
    try {
      await api.telegramLink(data);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Не удалось выполнить запрос");
    }
  }

  if (!me) return null;
  return (
    <div className="mx-auto max-w-sm">
      <h1 className="mb-4 text-2xl font-semibold">Аккаунт</h1>
      <dl className="mb-4 flex flex-col gap-2 text-sm">
        <div>
          <dt className="text-muted">Email</dt>
          <dd>{me.email ?? "не указан"}</dd>
        </div>
        <div>
          <dt className="text-muted">Telegram</dt>
          <dd>{me.telegram_linked ? (me.telegram_name ?? "привязан") : "не привязан"}</dd>
        </div>
      </dl>
      {error && <ErrorBanner message={error} />}
      {!me.telegram_linked && botUsername && (
        <div className="mt-2 flex flex-col items-start gap-2">
          <p className="text-sm text-muted">Привязать Telegram</p>
          <TelegramLogin botUsername={botUsername} onAuth={link} />
        </div>
      )}
    </div>
  );
}

export function AccountPage() {
  return (
    <RequireAuth>
      <Account />
    </RequireAuth>
  );
}
