type Props = { steps: string[]; current: number };

export function Steps({ steps, current }: Props) {
  return (
    <ol className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
      {steps.map((s, i) => (
        <li
          key={s}
          aria-current={i === current ? "step" : undefined}
          className={i === current ? "text-accent font-medium" : i < current ? "text-fg" : "text-muted"}
        >
          <span className="mr-1">{i + 1}.</span>
          {s}
        </li>
      ))}
    </ol>
  );
}
