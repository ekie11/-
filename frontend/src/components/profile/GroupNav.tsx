type Item = { id: string; label: string; diff: boolean };

export function GroupNav({ items, active, onSelect }: { items: Item[]; active: string; onSelect: (id: string) => void }) {
  return (
    <nav aria-label="Группы требований" className="flex flex-row gap-1 overflow-x-auto md:flex-col md:w-56 md:shrink-0">
      {items.map((g) => (
        <button
          key={g.id}
          type="button"
          data-diff={g.diff}
          aria-current={g.id === active ? "true" : undefined}
          onClick={() => onSelect(g.id)}
          className={`flex items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm whitespace-nowrap cursor-pointer ${g.id === active ? "bg-line font-medium" : "hover:bg-line"}`}
        >
          {g.label}
          {g.diff && <span aria-label="есть отличия от ГОСТа" className="inline-block h-2 w-2 rounded-full bg-accent" />}
        </button>
      ))}
    </nav>
  );
}
