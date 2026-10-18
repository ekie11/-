import { useEffect, useState } from "react";
import { apiFetch } from "./api";

export type GroupId = string;

export type FieldDef = {
  rule: string;
  path: string;
  group: GroupId;
  label: string;
  kind: "number" | "select" | "bool" | "text" | "fixed";
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: { value: string; label: string }[];
};

export type ProfileFieldsResponse = {
  groups: { id: GroupId; label: string }[];
  rule_labels: Record<string, string>;
  fields: FieldDef[];
  extraction_enabled: boolean;
};

export type ProfileFields = {
  groups: { id: GroupId; label: string }[];
  ruleLabels: Record<string, string>;
  fields: FieldDef[];
  extractionEnabled: boolean;
};

export type ProfileFieldsState =
  | { status: "loading" }
  | { status: "error" }
  | ({ status: "ready" } & ProfileFields);

/** Описание полей профиля — из API (единый источник: backend/profiles/fields.json). */
export function useProfileFields(): ProfileFieldsState {
  const [state, setState] = useState<ProfileFieldsState>({ status: "loading" });
  useEffect(() => {
    let alive = true;
    apiFetch<ProfileFieldsResponse>("/profile-fields").then(
      (d) => {
        if (alive) {
          setState({
            status: "ready",
            groups: d.groups,
            ruleLabels: d.rule_labels,
            fields: d.fields,
            extractionEnabled: d.extraction_enabled,
          });
        }
      },
      () => {
        if (alive) setState({ status: "error" });
      },
    );
    return () => {
      alive = false;
    };
  }, []);
  return state;
}
