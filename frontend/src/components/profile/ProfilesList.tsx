"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Select } from "@/components/ui/Select";
import { TextField } from "@/components/ui/TextField";
import { ApiError, apiFetch, apiUpload, type Profile, type ProfileSummary } from "@/lib/api";

export function ProfilesList() {
  const router = useRouter();
  const ret = useSearchParams().get("return") === "wizard" ? "?return=wizard" : "";
  const [list, setList] = useState<ProfileSummary[] | null>(null);
  const [baseId, setBaseId] = useState("");
  const [name, setName] = useState("Мой профиль");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiFetch<ProfileSummary[]>("/profiles")
      .then((l) => {
        setList(l);
        setBaseId((l.find((p) => p.readonly) ?? l[0])?.id ?? "");
      })
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Не удалось загрузить профили"));
  }, []);

  async function run(fn: () => Promise<Profile>) {
    setBusy(true);
    setError(null);
    try {
      const p = await fn();
      router.push(`/profiles/${p.id}${ret}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Не удалось выполнить действие");
      setBusy(false);
    }
  }

  const create = () =>
    run(() => apiFetch<Profile>("/profiles", { method: "POST", body: JSON.stringify({ base_id: baseId, name: name.trim() }) }));
  const importFile = (file: File) => {
    const form = new FormData();
    form.set("file", file);
    return run(() => apiUpload<Profile>("/profiles/import", form));
  };

  const own = (list ?? []).filter((p) => !p.readonly);
  const bases = (list ?? []).filter((p) => p.readonly);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Мои требования</h1>
      {error && <ErrorBanner message={error} />}
      {list !== null && own.length === 0 && <p className="text-muted">Своих профилей пока нет</p>}
      <ul className="flex flex-col gap-2">
        {own.map((p) => (
          <li key={p.id}>
            <Link href={`/profiles/${p.id}${ret}`} className="text-accent underline underline-offset-2">{p.name}</Link>
          </li>
        ))}
      </ul>
      <section className="flex flex-col gap-3 border-t border-line pt-5">
        <h2 className="text-lg font-medium">Создать на основе ГОСТа</h2>
        <Select label="ГОСТ" value={baseId} onChange={setBaseId} options={bases.map((b) => ({ value: b.id, label: b.name }))} />
        <TextField label="Название" value={name} onChange={(e) => setName(e.target.value)} />
        <div>
          <Button variant="primary" loading={busy} disabled={!baseId || !name.trim()} onClick={create}>
            Создать на основе ГОСТа
          </Button>
        </div>
      </section>
      <section className="flex flex-col gap-2 border-t border-line pt-5">
        <h2 className="text-lg font-medium">Импорт</h2>
        <label className="text-sm text-muted" htmlFor="profile-import">Файл профиля (JSON)</label>
        <input
          id="profile-import"
          type="file"
          accept="application/json,.json"
          disabled={busy}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void importFile(f);
          }}
        />
      </section>
    </div>
  );
}
