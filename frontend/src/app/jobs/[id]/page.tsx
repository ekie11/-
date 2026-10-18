import { JobResult } from "@/components/result/JobResult";

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <JobResult id={id} />;
}
