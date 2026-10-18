import { Suspense } from "react";
import { Wizard } from "@/components/wizard/Wizard";

export default function Home() {
  return (
    <Suspense fallback={null}>
      <Wizard />
    </Suspense>
  );
}
