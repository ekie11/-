"use client";

import { useBotUsername } from "@/lib/useBotUsername";

export function BotLink() {
  const username = useBotUsername();
  if (!username) return null;
  return (
    <p className="mt-6 text-sm text-muted">
      Бот в Telegram:{" "}
      <a href={`https://t.me/${username}`} className="text-accent underline underline-offset-2" target="_blank" rel="noreferrer">
        @{username}
      </a>
    </p>
  );
}
