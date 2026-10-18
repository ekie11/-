import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant: "primary" | "secondary" | "link";
  loading?: boolean;
};

const styles = {
  primary: "bg-accent text-white border border-accent hover:opacity-90 px-4 py-2 rounded-md",
  secondary: "bg-bg text-fg border border-line hover:border-muted px-4 py-2 rounded-md",
  link: "text-accent underline underline-offset-2 hover:opacity-80 px-0 py-0",
};

export function Button({ variant, loading, disabled, className = "", children, type = "button", ...rest }: Props) {
  return (
    <button
      type={type}
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading ? true : undefined}
      className={`${styles[variant]} text-sm font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
    >
      {loading ? "Подождите…" : children}
    </button>
  );
}
