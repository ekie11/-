"use client";

import { useRef, useState } from "react";

type Props = { file: File | null; error: string | null; onFile: (file: File) => void };

export function FileDrop({ file, error, onFile }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <div className="flex flex-col gap-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const f = e.dataTransfer.files[0];
          if (f) onFile(f);
        }}
        className={`flex flex-col items-center gap-2 rounded-md border border-dashed px-4 py-10 text-sm ${over ? "border-accent" : "border-line"}`}
      >
        <p className="text-muted">Перетащите файл сюда или выберите на компьютере</p>
        <label htmlFor="docx-file" className="cursor-pointer text-accent underline underline-offset-2">
          Выбрать файл .docx
        </label>
        <input
          ref={input}
          id="docx-file"
          type="file"
          accept=".docx"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFile(f);
            e.target.value = "";
          }}
        />
        <p className="text-muted">До 20 МБ</p>
      </div>
      {file && !error && <p className="text-sm">Выбран файл: {file.name}</p>}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
