"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ApiError, apiFetch, type Job } from "@/lib/api";
import { summary } from "@/lib/issues";
import { useMe } from "@/lib/useMe";
import { IssueList } from "./IssueList";

export const POLL_MS = 2000;

const linkBtn = "rounded-md border border-line px-4 py-2 text-sm font-medium hover:border-muted";

export function JobResult({ id }: { id: string }) {
  const { me } = useMe();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function tick() {
      try {
        const j = await apiFetch<Job>(`/jobs/${id}`);
        if (!alive) return;
        setJob(j);
        setError(null);
        if (j.status === "queued" || j.status === "running") timer = setTimeout(tick, POLL_MS);
      } catch (e) {
        if (!alive) return;
        setError(e instanceof ApiError ? e.detail : "Не удалось получить результат");
        // временные сбои (сеть, 5xx) — продолжаем опрос; 4xx окончательные
        if (!(e instanceof ApiError) || e.status === 0 || e.status >= 500) timer = setTimeout(tick, POLL_MS);
      }
    }
    void tick();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  const guestBanner = me === null && (
    <p className="rounded-md border border-line px-3 py-2 text-sm">
      Результат хранится 24 часа — зарегистрируйтесь, чтобы сохранить.{" "}
      <Link href={`/register?next=/jobs/${id}`} className="text-accent underline underline-offset-2">
        Зарегистрироваться
      </Link>
    </p>
  );

  if (!job) {
    return error ? <ErrorBanner message={error} /> : <p className="text-muted">Загружаем…</p>;
  }

  if (job.status === "queued" || job.status === "running") {
    return (
      <div className="flex flex-col gap-4">
        <p role="status">Обрабатываем…</p>
        {error && <ErrorBanner message={error} />}
        {guestBanner}
      </div>
    );
  }

  if (job.status === "error" || job.status === "expired") {
    const text =
      job.status === "expired" ? "Срок хранения результата истёк" : (job.error ?? "Не удалось обработать документ");
    return (
      <div className="flex flex-col gap-4">
        <ErrorBanner message={text} />
        <div>
          <Link href="/" className={linkBtn}>
            Попробовать снова
          </Link>
        </div>
      </div>
    );
  }

  const report = job.report ?? {};
  const issues = report.issues ?? [];
  return (
    <div className="flex flex-col gap-5">
      {guestBanner}
      <h1 className="text-xl font-semibold">{summary(report, job.mode)}</h1>
      {report.warnings?.map((w) => (
        <p key={w} className="text-sm text-muted">
          {w}
        </p>
      ))}
      <div className="flex flex-wrap gap-3">
        <a href={`/api/jobs/${id}/docx`} className={linkBtn}>
          Скачать DOCX
        </a>
        {job.has_pdf && (
          <a href={`/api/jobs/${id}/pdf`} className={linkBtn}>
            Скачать PDF
          </a>
        )}
        <Link href="/" className={linkBtn}>
          Проверить другой документ
        </Link>
      </div>
      <div className={`grid gap-6 ${job.has_pdf ? "lg:grid-cols-2" : ""}`}>
        <IssueList issues={issues} />
        {job.has_pdf && (
          <iframe
            title="Предпросмотр PDF"
            src={`/api/jobs/${id}/pdf`}
            className="h-[70vh] w-full rounded-md border border-line"
          />
        )}
      </div>
    </div>
  );
}
