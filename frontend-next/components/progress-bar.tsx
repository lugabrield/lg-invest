import { cn } from "@/lib/utils";
import type { StatusKind } from "@/lib/mock/dashboard";

const BAR_COLOR: Record<StatusKind, string> = {
  positive: "bg-positive",
  neutral: "bg-info",
  attention: "bg-attention",
  critical: "bg-critical",
  muted: "bg-text-faint",
};

interface ProgressBarProps {
  value: number; // 0-100
  status?: StatusKind;
  label?: string;
  className?: string;
}

/** ProgressBar — usado no PortfolioGauge e em barras de concentração/score. */
export function ProgressBar({ value, status = "neutral", label, className }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className={cn("w-full", className)}>
      {label && (
        <div className="mb-1.5 flex items-center justify-between text-xs text-text-muted">
          <span>{label}</span>
          <span className="font-medium text-text-primary">{clamped}</span>
        </div>
      )}
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-hover">
        <div
          className={cn("h-full rounded-full transition-all", BAR_COLOR[status])}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}

/** PortfolioGauge — variação semicircular do ProgressBar para o score
 * geral (Health Score / Conviction Score) no hero do Dashboard. */
export function PortfolioGauge({ value, label }: { value: number; label: string }) {
  const status: StatusKind = value >= 75 ? "positive" : value >= 50 ? "neutral" : value >= 25 ? "attention" : "critical";
  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="mb-3 text-sm font-medium text-text-primary">{label}</div>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-semibold text-text-primary">{value}</span>
        <span className="text-sm text-text-muted">/ 100</span>
      </div>
      <ProgressBar value={value} status={status} className="mt-4" />
    </div>
  );
}
