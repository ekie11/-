"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Steps } from "@/components/ui/Steps";
import { ApiError, apiFetch, apiUpload, type JobMode, type ProfileSummary } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { stepFromQuery, validateFile } from "@/lib/wizard";
import { StepDocument, type DocTab } from "./StepDocument";
import { StepRequirements } from "./StepRequirements";

export function Wizard() {
  const router = useRouter();
  const params = useSearchParams();
  const { me } = useMe();

  const [tab, setTab] = useState<DocTab>("file");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [profiles, setProfiles] = useState<ProfileSummary[] | null>(null);
  const [profileId, setProfileId] = useState<string>("");
  const [mode, setMode] = useState<JobMode>("check");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [limitReached, setLimitReached] = useState(false);
  const busy = useRef(false);

  const hasFile = file !== null && fileError === null;
  const hasInput = tab === "file" ? hasFile : text.trim() !== "";
  const step = stepFromQuery(params.get("step"), hasInput);
  const wantedProfile = params.get("profile");

  useEffect(() => {
    if (step !== 2 || profiles !== null) return;
    let alive = true;
    apiFetch<ProfileSummary[]>("/profiles")
      .then((list) => {
        if (!alive) return;
        setProfiles(list);
        const wanted = wantedProfile && list.find((p) => p.id === wantedProfile);
        const first = list.find((p) => p.readonly) ?? list[0];
        setProfileId((wanted || first)?.id ?? "");
      })
      .catch((e) => {
        if (alive) setError(e instanceof ApiError ? e.detail : "Не удалось загрузить профили");
      });
    return () => {
      alive = false;
    };
  }, [step, profiles, wantedProfile]);

  function onFile(f: File) {
    setFile(f);
    setFileError(validateFile(f));
  }

  function goStep(n: 1 | 2) {
    const q = new URLSearchParams(params.toString());
    q.set("step", String(n));
    router.push(`/?${q.toString()}`);
  }

  async function run() {
    if (busy.current) return;
    busy.current = true;
    setSubmitting(true);
    setError(null);
    setLimitReached(false);
    const form = new FormData();
    form.set("profile_id", profileId);
    form.set("mode", mode);
    if (tab === "file" && file) form.set("file", file);
    else form.set("text", text);
    try {
      const job = await apiUpload<{ id: number | string }>("/jobs", form);
      router.push(`/jobs/${job.id}`);
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.detail);
        setLimitReached(e.status === 429);
      } else {
        setError("Не удалось запустить обработку");
      }
      busy.current = false;
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-muted">Проверим и оформим документ по ГОСТ: загрузите файл, выберите требования и получите результат.</p>
      <div className="flex flex-col gap-6 rounded-md border border-line p-6">
        <Steps steps={["Документ", "Требования", "Результат"]} current={step - 1} />
        {step === 1 ? (
          <StepDocument
            tab={tab}
            onTab={setTab}
            file={file}
            fileError={fileError}
            onFile={onFile}
            text={text}
            onText={setText}
            canNext={hasInput}
            onNext={() => goStep(2)}
          />
        ) : (
          <StepRequirements
            profiles={profiles}
            profileId={profileId}
            onProfile={setProfileId}
            mode={mode}
            onMode={setMode}
            loggedIn={me !== null}
            submitting={submitting}
            error={error}
            limitReached={limitReached}
            onBack={() => router.back()}
            onRun={run}
          />
        )}
      </div>
    </div>
  );
}
