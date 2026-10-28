import { Suspense } from "react";
import { AccountPage } from "@/components/AccountPage";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <AccountPage />
    </Suspense>
  );
}
