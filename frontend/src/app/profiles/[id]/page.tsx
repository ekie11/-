"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";
import { ProfileEditor } from "@/components/profile/ProfileEditor";
import { RequireAuth } from "@/components/RequireAuth";

export default function ProfilePage() {
  const { id } = useParams<{ id: string }>();
  return (
    <Suspense>
      <RequireAuth>
        <main className="mx-auto max-w-5xl px-4 py-8">
          <ProfileEditor id={id} />
        </main>
      </RequireAuth>
    </Suspense>
  );
}
