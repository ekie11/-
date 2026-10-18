"use client";

import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Tabs } from "@/components/ui/Tabs";
import { FileDrop } from "@/components/wizard/FileDrop";

export type GuidelineTab = "file" | "text";

type Props = {
  tab: GuidelineTab;
  onTab: (t: GuidelineTab) => void;
  file: File | null;
  fileError: string | null;
  onFile: (f: File) => void;
  text: string;
  onText: (t: string) => void;
  bases: { value: string; label: string }[];
  baseId: string;
  onBase: (id: string) => void;
  quota: { used: number; limit: number } | null;
  busy: boolean;
  onSubmit: () => void;
};

export function UploadStep(p: Props) {
  const ready = p.tab === "file" ? p.file !== null && !p.fileError : p.text.trim() !== "";
  const left = p.quota ? Math.max(0, p.quota.limit - p.quota.used) : null;
  return (
    <div className="flex flex-col gap-4">
      <Tabs
        items={[
          { id: "file", label: "Загрузить файл" },
          { id: "text", label: "Вставить текст" },
        ]}
        value={p.tab}
        onChange={(id) => p.onTab(id as GuidelineTab)}
      />
      {p.tab === "file" ? (
        <FileDrop file={p.file} error={p.fileError} onFile={p.onFile} accept=".docx,.pdf" linkLabel="Выбрать файл DOCX или PDF" />
      ) : (
        <textarea
          aria-label="Текст методички"
          value={p.text}
          onChange={(e) => p.onText(e.target.value)}
          rows={12}
          placeholder="Вставьте текст методички"
          className="rounded-md border border-line bg-bg px-3 py-2 text-sm text-fg"
        />
      )}
      <Select label="Базовый ГОСТ" value={p.baseId} onChange={p.onBase} options={p.bases} />
      <div className="flex items-center gap-4">
        <Button variant="primary" loading={p.busy} disabled={!ready || left === 0} onClick={p.onSubmit}>
          Извлечь требования
        </Button>
        {p.quota && <span className="text-sm text-muted">Осталось {left} из {p.quota.limit} на сегодня</span>}
      </div>
    </div>
  );
}
