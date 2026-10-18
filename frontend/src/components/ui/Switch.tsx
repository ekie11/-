type Props = { checked: boolean; onChange: (checked: boolean) => void; label: string };

export function Switch({ checked, onChange, label }: Props) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="inline-flex items-center gap-2 text-sm text-fg cursor-pointer"
    >
      <span className={`relative inline-block h-5 w-9 rounded-full border ${checked ? "bg-accent border-accent" : "bg-line border-line"}`}>
        <span className={`absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white ${checked ? "left-[18px]" : "left-0.5"}`} />
      </span>
      {label}
    </button>
  );
}
