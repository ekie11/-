import { Suspense } from "react";
import { ProfilesList } from "@/components/profile/ProfilesList";
import { RequireAuth } from "@/components/RequireAuth";

export default function ProfilesPage() {
  return (
    <Suspense>
      <RequireAuth>
        <main className="mx-auto max-w-3xl px-4 py-8">
          <ProfilesList />
        </main>
      </RequireAuth>
    </Suspense>
  );
}
