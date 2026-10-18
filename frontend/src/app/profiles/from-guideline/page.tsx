import { Suspense } from "react";
import { FromGuideline } from "@/components/extraction/FromGuideline";
import { RequireAuth } from "@/components/RequireAuth";

export default function FromGuidelinePage() {
  return (
    <Suspense>
      <RequireAuth>
        <main className="mx-auto max-w-4xl px-4 py-8">
          <FromGuideline />
        </main>
      </RequireAuth>
    </Suspense>
  );
}
