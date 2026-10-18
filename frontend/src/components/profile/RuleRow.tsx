import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Switch } from "@/components/ui/Switch";
import { TextField } from "@/components/ui/TextField";
import { differs, getAt, setAt } from "@/lib/profileForm";
import { RULE_LABELS, type FieldDef } from "@/lib/ruleSchema";

type Rule = { value?: unknown; severity?: string; enabled?: boolean; source?: string; [k: string]: unknown };

type Props = {
  ruleId: string;
  fields: FieldDef[];
  rule: Rule;
  baseRule?: Rule;
  disabled: boolean;
  onChange: (rule: Rule) => void;
};

function show(f: FieldDef, v: unknown): string {
  if (f.kind === "bool") return v ? "да" : "нет";
  if (f.kind === "select") return f.options?.find((o) => o.value === v)?.label ?? String(v);
  return `${String(v)}${f.unit ? ` ${f.unit}` : ""}`;
}

function NumberField({ f, value, disabled, onCommit }: { f: FieldDef; value?: number; disabled: boolean; onCommit: (n: number) => void }) {
  // Текст хранится отдельно, чтобы поле можно было очистить и набрать заново.
  const [text, setText] = useState<string | null>(null);
  return (
    <TextField
      label={f.label}
      type="number"
      min={f.min}
      max={f.max}
      step={f.step}
      disabled={disabled}
      value={text ?? (value === undefined ? "" : String(value))}
      onChange={(e) => {
        setText(e.target.value);
        const n = e.currentTarget.valueAsNumber;
        if (!Number.isNaN(n)) onCommit(n);
      }}
      onBlur={() => {
        const n = Number(text);
        if (text !== null && text !== "" && !Number.isNaN(n)) {
          const c = Math.min(f.max ?? n, Math.max(f.min ?? n, n));
          if (c !== n || c !== value) onCommit(c);
        } else if (text === "" && value !== undefined && f.min !== undefined) {
          onCommit(value);
        }
        setText(null);
      }}
    />
  );
}

export function RuleRow({ ruleId, fields, rule, baseRule, disabled, onChange }: Props) {
  const diff = differs(rule, baseRule);
  const set = (path: string, v: unknown) => onChange({ ...rule, value: setAt(rule.value, path, v) });
  return (
    <fieldset
      data-differs={diff}
      className={`flex flex-col gap-3 rounded-md border px-4 py-3 ${diff ? "border-accent bg-line" : "border-line"}`}
    >
      <legend className="px-1 text-sm font-medium">{RULE_LABELS[ruleId] ?? ruleId}</legend>
      <div className="flex flex-wrap items-center gap-4">
        <Switch label="проверять" checked={rule.enabled !== false} onChange={(c) => !disabled && onChange({ ...rule, enabled: c })} />
        <span className="text-sm text-muted">{rule.severity === "recommendation" ? "рекомендация" : "ошибка"}</span>
        {diff && !disabled && (
          <Button variant="link" className="text-sm" onClick={() => baseRule && onChange(structuredClone(baseRule))}>
            вернуть как в ГОСТе
          </Button>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {fields.map((f) => {
          const v = getAt(rule.value, f.path);
          const hint = baseRule ? `по ГОСТ: ${show(f, getAt(baseRule.value, f.path))}${baseRule.source ? `, ${baseRule.source}` : ""}` : null;
          return (
            <div key={f.path} className="flex flex-col gap-1">
              {f.kind === "number" && (
                <NumberField f={f} value={typeof v === "number" ? v : undefined} disabled={disabled} onCommit={(n) => set(f.path, n)} />
              )}
              {f.kind === "text" && (
                <TextField label={f.label} disabled={disabled} value={typeof v === "string" ? v : ""} onChange={(e) => set(f.path, e.target.value)} />
              )}
              {f.kind === "fixed" && (
                <div className="flex flex-col gap-1">
                  <span className="text-sm text-muted">{f.label}</span>
                  <span className="text-sm" data-fixed={f.path}>
                    {f.options?.find((o) => o.value === String(v))?.label ?? String(v)}
                  </span>
                  {!f.options?.some((o) => o.value === String(v)) && (
                    <span role="alert" className="text-xs text-red-700">
                      Это значение не поддерживается — будет использовано: {f.options?.[0]?.label}
                    </span>
                  )}
                  <span className="text-xs text-muted">Пока поддерживается только это значение</span>
                </div>
              )}
              {f.kind === "select" && (
                <fieldset disabled={disabled} className="contents">
                  <Select label={f.label} options={f.options ?? []} value={String(v ?? "")} onChange={(x) => set(f.path, x)} />
                </fieldset>
              )}
              {f.kind === "bool" && (
                <fieldset disabled={disabled} className="contents">
                  <Switch label={f.label} checked={v === true} onChange={(c) => !disabled && set(f.path, c)} />
                </fieldset>
              )}
              {f.kind === "number" && f.unit && <span className="text-xs text-muted">{f.unit}</span>}
              {hint && <span className="text-xs text-muted">{hint}</span>}
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}
