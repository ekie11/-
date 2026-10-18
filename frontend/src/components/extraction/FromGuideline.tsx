"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ApiError, api, apiFetch, type Extraction, type Profile, type ProfileSummary } from "@/lib/api";
import { useProfileFields } from "@/lib/fields";
import { ResultTable } from "./ResultTable";
import { UploadStep, type GuidelineTab } from "./UploadStep";

export const POLL_MS = 2000;
const MAX_FILE = 20 * 1024 * 1024;
const DEFAULT_BASE = "gost-7.32-2017";

const msg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.detail : fallback);

export function FromGuideline() {
  const router = useRouter();
  const pf = useProfileFields();
  const [tab, setTab] = useState<GuidelineTab>("file");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [bases, setBases] = useState<{ value: string; label: string }[]>([]);
  const [baseId, setBaseId] = useState(DEFAULT_BASE);
  const [quota, setQuota] = useState<{ used: number; limit: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [extractionId, setExtractionId] = useState<string | null>(null);
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [baseProfile, setBaseProfile] = useState<Profile | null>(null);
  const [accepted, setAccepted] = useState<number[]>([]);
  const [name, setName] = useState("");

  useEffect(() => {
    apiFetch<ProfileSummary[]>("/profiles").then(
      (l) => {
        const b = l.filter((p) => p.readonly).map((p) => ({ value: p.id, label: p.name }));
        setBases(b);
        if (b.length > 0 && !b.some((x) => x.value === DEFAULT_BASE)) setBaseId(b[0].value);
      },
      () => undefined,
    );
    api.getQuota().then(setQuota, () => undefined);
  }, []);

  useEffect(() => {
    if (!extractionId) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function tick() {
      try {
        const e = await api.getExtraction(extractionId!);
        if (!alive) return;
        if (e.status === "done" && e.result) {
          setAccepted(e.result.found.map((_, i) => i));
          setName(e.source_name ? e.source_name.replace(/\.[^.]+$/, "") : "Профиль из методички");
          apiFetch<Profile>(`/profiles/${e.base_profile_id}`).then(
            (p) => alive && setBaseProfile(p),
            () => undefined,
          );
        }
        setExtraction(e);
        if (e.status === "queued" || e.status === "running") timer = setTimeout(tick, POLL_MS);
      } catch (e) {
        if (!alive) return;
        if (!(e instanceof ApiError) || e.status === 0 || e.status >= 500) {
          timer = setTimeout(tick, POLL_MS);
        } else {
          setError(e.detail);
          setExtractionId(null);
        }
      }
    }
    void tick();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [extractionId]);

  const done = extraction?.status === "done" ? extraction : null;

  function pickFile(f: File) {
    setFile(f);
    setFileError(/\.(docx|pdf)$/i.test(f.name) ? (f.size > MAX_FILE ? "Файл больше 20 МБ" : null) : "Нужен файл DOCX или PDF");
  }

  async function submit() {
    setBusy(true);
    setError(null);
    const form = new FormData();
    if (tab === "file" && file) form.set("file", file);
    else form.set("text", text);
    form.set("base_profile_id", baseId);
    try {
      const { id } = await api.createExtraction(form);
      setExtraction(null);
      setBaseProfile(null);
      setExtractionId(id);
    } catch (e) {
      setError(msg(e, "Не удалось отправить методичку"));
    } finally {
      setBusy(false);
      api.getQuota().then(setQuota, () => undefined);
    }
  }

  function reset() {
    setExtractionId(null);
    setExtraction(null);
    setError(null);
  }

  async function create() {
    if (!extractionId) return;
    setBusy(true);
    setError(null);
    try {
      const { profile_id } = await api.createProfileFromExtraction(extractionId, { accepted, name: name.trim() });
      router.push(`/profiles/${profile_id}`);
    } catch (e) {
      setError(msg(e, "Не удалось создать профиль"));
      setBusy(false);
    }
  }

  let body;
  if (pf.status === "loading") body = <p className="text-muted">Загрузка…</p>;
  else if (pf.status === "error") body = <ErrorBanner message="Не удалось загрузить описание полей" />;
  else if (!extractionId) {
    body = (
      <UploadStep
        tab={tab}
        onTab={setTab}
        file={file}
        fileError={fileError}
        onFile={pickFile}
        text={text}
        onText={setText}
        bases={bases}
        baseId={baseId}
        onBase={setBaseId}
        quota={quota}
        busy={busy}
        onSubmit={submit}
      />
    );
  } else if (extraction?.status === "failed") {
    body = (
      <div className="flex flex-col gap-4">
        <ErrorBanner message={extraction.error ?? "Не удалось прочитать методичку"} />
        <div>
          <Button variant="primary" onClick={reset}>Попробовать снова</Button>
        </div>
      </div>
    );
  } else if (done?.result) {
    body = (
      <ResultTable
        result={done.result}
        fields={pf.fields}
        groups={pf.groups}
        baseRules={baseProfile?.rules ?? {}}
        accepted={accepted}
        onAccepted={setAccepted}
        name={name}
        onName={setName}
        onCreate={create}
        onBack={reset}
        busy={busy}
      />
    );
  } else {
    body = <p role="status">Читаем методичку… обычно до минуты</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Создать из методички</h1>
      {error && <ErrorBanner message={error} />}
      {body}
    </div>
  );
}
