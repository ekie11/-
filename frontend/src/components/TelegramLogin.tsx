"use client";

import { useEffect, useId, useRef } from "react";
import type { TelegramAuthData } from "@/lib/api";

type Props = { botUsername: string | null; onAuth: (data: TelegramAuthData) => void };

declare global {
  interface Window {
    [key: string]: unknown;
  }
}

/** Официальный виджет Telegram Login; callback регистрируется глобально под уникальным именем. */
export function TelegramLogin({ botUsername, onAuth }: Props) {
  const holder = useRef<HTMLDivElement>(null);
  const onAuthRef = useRef(onAuth);
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");

  useEffect(() => {
    onAuthRef.current = onAuth;
  });

  useEffect(() => {
    const el = holder.current;
    if (!botUsername || !el) return;
    const callback = `onTelegramAuth_${id}`;
    window[callback] = (user: TelegramAuthData) => onAuthRef.current(user);
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-onauth", `${callback}(user)`);
    el.appendChild(script);
    return () => {
      delete window[callback];
      el.replaceChildren();
    };
  }, [botUsername, id]);

  if (!botUsername) return null;
  return <div ref={holder} data-testid="telegram-login" />;
}
