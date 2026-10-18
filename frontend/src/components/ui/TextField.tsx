import { useId, type InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string };

export function TextField({ label, error, id, className = "", ...rest }: Props) {
  const auto = useId();
  const inputId = id ?? auto;
  const errId = `${inputId}-error`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={inputId} className="text-sm text-muted">{label}</label>
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errId : undefined}
        className={`border ${error ? "border-red-700" : "border-line"} bg-bg text-fg rounded-md px-3 py-2 text-sm ${className}`}
        {...rest}
      />
      {error && <p id={errId} className="text-sm text-red-700">{error}</p>}
    </div>
  );
}
