"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ApiError, apiFetch, type JobSummary } from "@/lib/api";
import { format } from "@/lib/format";

export function DocumentsTable() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<JobSummary[]>("/jobs")
      .then(setJobs)
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Не удалось загрузить документы"));
  }, []);

  if (error) return <ErrorBanner message={error} />;
  if (jobs === null) return <p className="text-sm text-muted">Загружаем…</p>;
  if (jobs.length === 0) {
    return (
      <p className="text-muted">
        <span>Пока нет документов</span>{". "}
        <Link href="/" className="text-accent underline underline-offset-2">Перейти к мастеру</Link>
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-line text-muted">
          <tr>
            <th scope="col" className="py-2 pr-4 font-medium">Дата</th>
            <th scope="col" className="py-2 pr-4 font-medium">Профиль</th>
            <th scope="col" className="py-2 pr-4 font-medium">Режим</th>
            <th scope="col" className="py-2 pr-4 font-medium">Статус</th>
            <th scope="col" className="py-2 font-medium">Хранится до</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} className="border-b border-line">
              <td className="py-2 pr-4">
                <Link href={`/jobs/${j.id}`} className="text-accent underline underline-offset-2">
                  {format.dateTime(j.created_at)}
                </Link>
              </td>
              <td className="py-2 pr-4">{j.profile_name}</td>
              <td className="py-2 pr-4">{format.modeLabel(j.mode)}</td>
              <td className="py-2 pr-4">{format.statusLabel(j.status)}</td>
              <td className="py-2">{j.expires_at ? format.dateTime(j.expires_at) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
