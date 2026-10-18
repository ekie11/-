import { Suspense } from "react";
import { DocumentsTable } from "@/components/DocumentsTable";
import { RequireAuth } from "@/components/RequireAuth";

export default function DocumentsPage() {
  return (
    <Suspense>
      <RequireAuth>
        <h1 className="mb-6 text-2xl font-semibold">Мои документы</h1>
        <DocumentsTable />
      </RequireAuth>
    </Suspense>
  );
}
