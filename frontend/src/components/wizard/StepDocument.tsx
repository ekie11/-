"use client";

import { Button } from "@/components/ui/Button";
import { Tabs } from "@/components/ui/Tabs";
import { FileDrop } from "./FileDrop";

export type DocTab = "file" | "text";

type Props = {
  tab: DocTab;
  onTab: (t: DocTab) => void;
  file: File | null;
  fileError: string | null;
  onFile: (f: File) => void;
  text: string;
  onText: (t: string) => void;
  canNext: boolean;
  onNext: () => void;
};

export function StepDocument(p: Props) {
  return (
    <div className="flex flex-col gap-4">
      <Tabs
        items={[
          { id: "file", label: "Загрузить DOCX" },
          { id: "text", label: "Вставить текст" },
        ]}
        value={p.tab}
        onChange={(id) => p.onTab(id as DocTab)}
      />
      {p.tab === "file" ? (
        <FileDrop file={p.file} error={p.fileError} onFile={p.onFile} />
      ) : (
        <textarea
          aria-label="Текст документа"
          value={p.text}
          onChange={(e) => p.onText(e.target.value)}
          rows={12}
          placeholder="Вставьте текст документа"
          className="rounded-md border border-line bg-bg px-3 py-2 text-sm text-fg"
        />
      )}
      <div>
        <Button variant="primary" disabled={!p.canNext} onClick={p.onNext}>
          Далее
        </Button>
      </div>
    </div>
  );
}
