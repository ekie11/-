type Props = { items: { id: string; label: string }[]; value: string; onChange: (id: string) => void };

export function Tabs({ items, value, onChange }: Props) {
  return (
    <div role="tablist" className="flex gap-4 border-b border-line">
      {items.map((it) => {
        const selected = it.id === value;
        return (
          <button
            key={it.id}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(it.id)}
            className={`-mb-px border-b-2 px-1 py-2 text-sm cursor-pointer ${selected ? "border-accent text-accent font-medium" : "border-transparent text-muted hover:text-fg"}`}
          >
            {it.label}
          </button>
        );
      })}
    </div>
  );
}
