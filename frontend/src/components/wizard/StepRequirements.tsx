"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Select } from "@/components/ui/Select";
import type { JobMode, ProfileSummary } from "@/lib/api";

type Props = {
  profiles: ProfileSummary[] | null;
  profileId: string;
  onProfile: (id: string) => void;
  mode: JobMode;
  onMode: (m: JobMode) => void;
  loggedIn: boolean;
  submitting: boolean;
  error: string | null;
  limitReached: boolean;
  onBack: () => void;
  onRun: () => void;
};

const MODES: { id: JobMode; title: string; hint: string }[] = [
  { id: "check", title: "Проверить", hint: "оставим комментарии" },
  { id: "format", title: "Оформить", hint: "исправим сами" },
];

export function StepRequirements(p: Props) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <Select
          label="Требования"
          value={p.profileId}
          onChange={p.onProfile}
          options={(p.profiles ?? []).map((x) => ({ value: x.id, label: x.name }))}
        />
        {p.loggedIn ? (
          <Link href="/profiles?return=wizard" className="text-sm text-accent underline underline-offset-2">
            Настроить свои требования
          </Link>
        ) : (
          <p className="text-sm text-muted">
            <Link href="/register?next=/" className="text-accent underline underline-offset-2">
              Свои требования — после регистрации
            </Link>
          </p>
        )}
      </div>
      <fieldset className="flex flex-col gap-2 sm:flex-row">
        <legend className="sr-only">Режим</legend>
        {MODES.map((m) => (
          <label
            key={m.id}
            className={`flex flex-1 cursor-pointer flex-col rounded-md border px-4 py-3 text-sm ${p.mode === m.id ? "border-accent" : "border-line"}`}
          >
            <input
              type="radio"
              name="mode"
              className="sr-only"
              checked={p.mode === m.id}
              onChange={() => p.onMode(m.id)}
            />
            <span className="font-medium">{m.title}</span>
            <span className="text-muted">{m.hint}</span>
          </label>
        ))}
      </fieldset>
      {p.error && <ErrorBanner message={p.error} />}
      {p.limitReached && (
        <Link href="/register?next=/" className="text-sm text-accent underline underline-offset-2">
          Зарегистрироваться
        </Link>
      )}
      <div className="flex gap-3">
        <Button variant="secondary" onClick={p.onBack}>
          Назад
        </Button>
        <Button variant="primary" loading={p.submitting} disabled={!p.profileId} onClick={p.onRun}>
          Запустить
        </Button>
      </div>
    </div>
  );
}
