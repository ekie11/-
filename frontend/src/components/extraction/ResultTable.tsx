"use client";

import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import type { RuleConfig } from "@/lib/api";
import type { FieldDef } from "@/lib/fields";

export type FoundItem = { rule: string; path: string; value: unknown; quote: string; page: number | null };
export type UnsupportedItem = { text: string; quote: string; page: number | null };
export type ExtractionResult = { found: FoundItem[]; unsupported: UnsupportedItem[]; rejected_count: number };

type Props = {
  result: ExtractionResult;
  fields: FieldDef[];
  groups: { id: string; label: string }[];
  baseRules: RuleConfig;
  accepted: number[];
  onAccepted: (a: number[]) => void;
  name: string;
  onName: (n: string) => void;
  onCreate: () => void;
  onBack: () => void;
  busy: boolean;
};

export function formatValue(f: FieldDef | undefined, v: unknown): string {
  if (v === undefined || v === null) return "—";
  if (f?.kind === "bool") return v ? "да" : "нет";
  if (f?.kind === "select") return f.options?.find((o) => o.value === v)?.label ?? String(v);
  return f?.unit ? `${v} ${f.unit}` : String(v);
}

function baseValue(rules: RuleConfig, item: FoundItem): unknown {
  const rule = rules[item.rule] as { value?: Record<string, unknown> } | undefined;
  return rule?.value?.[item.path];
}

function cite(quote: string, page: number | null) {
  return page ? `«${quote}» (стр. ${page})` : `«${quote}»`;
}

export function ResultTable(p: Props) {
  const { found, unsupported } = p.result;
  const groupLabel = (id?: string) => p.groups.find((g) => g.id === id)?.label ?? "";

  const unsupportedBlock = unsupported.length > 0 && (
    <section className="flex flex-col gap-2 border-t border-line pt-4">
      <h2 className="text-lg font-medium">Найдено, но пока не поддерживается</h2>
      <ul className="flex flex-col gap-2 text-sm">
        {unsupported.map((u, i) => (
          <li key={i}>
            <p>{u.text}</p>
            <p className="text-muted">{cite(u.quote, u.page)}</p>
          </li>
        ))}
      </ul>
    </section>
  );

  if (found.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <p>Не нашли требований к оформлению — это точно методичка?</p>
        <div>
          <Button variant="secondary" onClick={p.onBack}>Назад</Button>
        </div>
        {unsupportedBlock}
      </div>
    );
  }

  const all = found.map((_, i) => i);
  const toggle = (i: number) =>
    p.onAccepted(p.accepted.includes(i) ? p.accepted.filter((x) => x !== i) : all.filter((x) => x === i || p.accepted.includes(x)));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-4 text-sm">
        <Button variant="link" onClick={() => p.onAccepted(all)}>Выбрать все</Button>
        <Button variant="link" onClick={() => p.onAccepted([])}>Снять все</Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line text-muted">
              <th className="py-2 pr-2"><span className="sr-only">Принять</span></th>
              <th className="py-2 pr-3">Группа</th>
              <th className="py-2 pr-3">Требование</th>
              <th className="py-2 pr-3">Из методички</th>
              <th className="py-2 pr-3">В ГОСТе</th>
              <th className="py-2">Цитата</th>
            </tr>
          </thead>
          <tbody>
            {found.map((it, i) => {
              const f = p.fields.find((x) => x.rule === it.rule && x.path === it.path);
              const bv = baseValue(p.baseRules, it);
              const same = bv !== undefined && String(bv) === String(it.value);
              return (
                <tr key={i} className={`border-b border-line align-top ${same ? "opacity-50" : ""}`}>
                  <td className="py-2 pr-2">
                    <input
                      type="checkbox"
                      aria-label={f?.label ?? `${it.rule} ${it.path}`}
                      checked={p.accepted.includes(i)}
                      onChange={() => toggle(i)}
                    />
                  </td>
                  <td className="py-2 pr-3">{groupLabel(f?.group)}</td>
                  <td className="py-2 pr-3">{f?.label ?? it.path}</td>
                  <td className="py-2 pr-3 font-medium">{formatValue(f, it.value)}</td>
                  <td className="py-2 pr-3">{formatValue(f, bv)}</td>
                  <td className="py-2 text-muted">{cite(it.quote, it.page)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {unsupportedBlock}
      <div className="flex flex-col gap-3 border-t border-line pt-4">
        <TextField label="Название профиля" value={p.name} onChange={(e) => p.onName(e.target.value)} />
        <div className="flex gap-3">
          <Button variant="primary" loading={p.busy} disabled={!p.name.trim()} onClick={p.onCreate}>Создать профиль</Button>
          <Button variant="secondary" onClick={p.onBack}>Назад</Button>
        </div>
      </div>
    </div>
  );
}
