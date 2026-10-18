import type { Issue } from "@/lib/api";
import { groupIssues } from "@/lib/issues";

export function IssueList({ issues }: { issues: Issue[] }) {
  const groups = groupIssues(issues);
  if (groups.length === 0) return null;
  return (
    <div className="flex flex-col gap-4">
      {groups.map((g) => (
        <section key={g.rule} className="rounded-md border border-line p-4">
          <h3 className="text-sm font-medium">
            {g.rule}
            {g.source && <span className="ml-2 font-normal text-muted">{g.source}</span>}
          </h3>
          <ul className="mt-2 flex flex-col gap-2 text-sm">
            {g.items.map((it, i) => (
              <li key={i}>
                <p>{it.message}</p>
                {(it.expected || it.actual) && (
                  <p className="text-muted">
                    {it.expected ? `Нужно: ${it.expected}` : null}
                    {it.expected && it.actual ? ". " : null}
                    {it.actual ? `Сейчас: ${it.actual}` : null}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
