import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { cx } from "@/lib/utils";
import { FiAlertCircle, FiInbox } from "react-icons/fi";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        "rounded-xl2 border border-base-border bg-base-surface shadow-soft",
        className
      )}
      {...props}
    />
  );
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  disabled,
  ...props
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]";
  const sizes =
    size === "sm" ? "px-3 py-1.5 text-sm" : size === "lg" ? "px-6 py-3 text-base" : "px-5 py-2.5 text-sm";
  const variants: Record<string, string> = {
    primary: "bg-signal text-white hover:brightness-110 shadow-[0_1px_0_rgba(255,255,255,0.15)_inset]",
    secondary:
      "bg-base-surface2 text-ink border border-base-border hover:bg-base-border/60",
    ghost: "text-ink-muted hover:text-ink hover:bg-base-surface2",
  };
  return (
    <button
      className={cx(base, sizes, variants[variant], className)}
      disabled={disabled}
      {...props}
    />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cx("animate-pulseSlow rounded-md bg-base-surface2", className)}
      aria-hidden="true"
    />
  );
}

export function EmptyState({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl2 border border-dashed border-base-border py-16 text-center">
      <div className="text-ink-faint text-2xl">{icon ?? <FiInbox />}</div>
      <p className="text-ink font-medium">{title}</p>
      <p className="text-ink-muted text-sm max-w-sm">{description}</p>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-xl2 border border-grade-strong_no_hire/30 bg-grade-strong_no_hire/5 py-16 text-center px-6">
      <div className="text-grade-strong_no_hire text-2xl">
        <FiAlertCircle />
      </div>
      <div>
        <p className="text-ink font-medium">The review couldn't be completed</p>
        <p className="text-ink-muted text-sm max-w-md mt-1">{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function Badge({
  children,
  color,
  className,
}: {
  children: ReactNode;
  color?: string;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        className
      )}
      style={
        color
          ? {
              color,
              backgroundColor: `${color}1A`,
              border: `1px solid ${color}40`,
            }
          : undefined
      }
    >
      {children}
    </span>
  );
}
