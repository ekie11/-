"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { Button } from "./ui/Button";

export function Header() {
  const { me, refresh } = useMe();
  const router = useRouter();

  async function logout() {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      /* сервер недоступен — всё равно обновляем состояние и уходим на главную */
    } finally {
      await refresh();
      router.push("/");
    }
  }

  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 text-sm">
        <Link href="/" className="text-base font-semibold text-fg">ГОСТ-сервис</Link>
        <nav className="flex flex-1 flex-wrap items-center gap-x-4 gap-y-1">
          <Link href="/documents" className="text-fg hover:text-accent">Мои документы</Link>
          {me && <Link href="/profiles" className="text-fg hover:text-accent">Мои профили</Link>}
        </nav>
        {me ? (
          <div className="flex items-center gap-3">
            <span className="text-muted">{me.email}</span>
            <Button variant="link" onClick={logout}>Выйти</Button>
          </div>
        ) : (
          <Link href="/login" className="text-accent hover:opacity-80">Войти</Link>
        )}
      </div>
    </header>
  );
}
