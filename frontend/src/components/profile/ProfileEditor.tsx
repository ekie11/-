"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { TextField } from "@/components/ui/TextField";
import { ApiError, apiFetch, type Profile } from "@/lib/api";
import { useProfileFields, type FieldDef } from "@/lib/fields";
import { groupHasDiff, unknownRules } from "@/lib/profileForm";
import { GroupNav } from "./GroupNav";
import { RuleRow } from "./RuleRow";

const OTHER = "other";
type Rules = Profile["rules"];
type Rule = React.ComponentProps<typeof RuleRow>["rule"];

function msg(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.detail : fallback;
}

export function ProfileEditor({ id }: { id: string }) {
  const router = useRouter();
  const isWizard = useSearchParams().get("return") === "wizard";
  const [loaded, setLoaded] = useState<Profile | null>(null);
  const [base, setBase] = useState<Profile | null>(null);
  const [name, setName] = useState("");
  const [rules, setRules] = useState<Rules>({});
  const pf = useProfileFields();
  const fields = useMemo(() => (pf.status === "ready" ? pf.fields : []), [pf]);
  const [group, setGroup] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const p = await apiFetch<Profile>(`/profiles/${id}`);
        if (!alive) return;
        setLoaded(p);
        setName(p.name);
        setRules(p.rules);
        // Для сравнения нужен ГОСТ: у собственного профиля это его база, у встроенного — он сам.
        const b = p.base ? await apiFetch<Profile>(`/profiles/${p.base}`) : p;
        if (alive) setBase(b);
      } catch (e) {
        if (alive) setError(msg(e, "Не удалось загрузить профиль"));
      }
    })();
    return () => {
      alive = false;
    };
  }, [id]);

  const dirty = loaded !== null && (name !== loaded.name || JSON.stringify(rules) !== JSON.stringify(loaded.rules));

  useEffect(() => {
    if (!dirty) return;
    const h = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);

  const current = useMemo(() => ({ rules }), [rules]);
  const others = useMemo(() => unknownRules(current, fields), [current, fields]);

  if (pf.status === "error") return <ErrorBanner message="Не удалось загрузить описание полей" />;
  if (!loaded || pf.status !== "ready") return error ? <ErrorBanner message={error} /> : <p className="text-muted">Загрузка…</p>;
  const { groups, ruleLabels } = pf;
  const activeGroup = group ?? groups[0].id;

  const readonly = loaded.readonly;
  const ret = isWizard ? "?return=wizard" : "";
  const navItems = [
    ...groups.map((g) => ({ id: g.id, label: g.label, diff: groupHasDiff(current, base, g.id, fields) })),
    ...(others.length ? [{ id: OTHER, label: "Другое", diff: false }] : []),
  ];

  const ruleIds = [...new Set(fields.filter((f) => f.group === activeGroup).map((f) => f.rule))].filter((r) => r in rules);
  const byRule = (r: string): FieldDef[] => fields.filter((f) => f.rule === r);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const saved = await apiFetch<Profile>(`/profiles/${id}`, { method: "PUT", body: JSON.stringify({ name, rules }) });
      setLoaded(saved);
      setName(saved.name);
      setRules(saved.rules);
      if (isWizard) router.push(`/?profile=${id}`);
    } catch (e) {
      setError(msg(e, "Не удалось сохранить"));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Удалить профиль?")) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/profiles/${id}`, { method: "DELETE" });
      router.push("/profiles");
    } catch (e) {
      setError(msg(e, "Не удалось удалить"));
      setBusy(false);
    }
  }

  async function copy() {
    setBusy(true);
    setError(null);
    try {
      const p = await apiFetch<Profile>("/profiles", {
        method: "POST",
        body: JSON.stringify({ base_id: id, name: `${loaded!.name} (мой)` }),
      });
      router.push(`/profiles/${p.id}${ret}`);
    } catch (e) {
      setError(msg(e, "Не удалось создать профиль"));
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-64 flex-1">
          <TextField label="Название" value={name} disabled={readonly} onChange={(e) => setName(e.target.value)} />
          {loaded.base && base && <p className="mt-1 text-sm text-muted">на основе {base.name}</p>}
        </div>
        {readonly ? (
          <Button variant="primary" loading={busy} onClick={copy}>Создать свой на основе</Button>
        ) : (
          <>
            <Button variant="primary" loading={busy} onClick={save}>Сохранить</Button>
            <a href={`/api/profiles/${id}/export`} className="text-sm text-accent underline underline-offset-2 py-2">Экспорт JSON</a>
            <Button variant="secondary" disabled={busy} onClick={remove}>Удалить</Button>
          </>
        )}
      </div>
      {error && <ErrorBanner message={error} />}
      <div className="flex flex-col gap-4 md:flex-row">
        <GroupNav items={navItems} active={activeGroup} onSelect={setGroup} />
        <div className="flex flex-1 flex-col gap-3">
          {activeGroup === OTHER ? (
            others.map((r) => (
              <div key={r} className="rounded-md border border-line px-4 py-3">
                <p className="text-sm font-medium">{r}</p>
                <pre className="mt-2 overflow-x-auto text-xs text-muted">{JSON.stringify(rules[r], null, 2)}</pre>
              </div>
            ))
          ) : ruleIds.length === 0 ? (
            <p className="text-muted">Для этого профиля настроек нет</p>
          ) : (
            ruleIds.map((r) => (
              <RuleRow
                key={r}
                label={ruleLabels[r] ?? r}
                fields={byRule(r)}
                rule={rules[r] as Rule}
                baseRule={base?.rules[r] as Rule | undefined}
                disabled={readonly}
                onChange={(nr) => setRules((prev) => ({ ...prev, [r]: nr }))}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

