"use client";

import { useEffect, useState } from "react";
import { api } from "./api";

/** Имя Telegram-бота из /config; null, пока не загружено, при ошибке или если бот выключен. */
export function useBotUsername(): string | null {
  const [username, setUsername] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    api
      .config()
      .then((c) => {
        if (alive) setUsername(c.telegram_bot_username ?? null);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);
  return username;
}
