import type { LucideIcon } from "lucide-react";
import {
  Globe,
  Heart,
  PieChart as PieChartIcon,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { StatusKind } from "@/lib/mock/dashboard";

const ICONS: Record<string, LucideIcon> = {
  wallet: Wallet,
  "trending-up": TrendingUp,
  globe: Globe,
  "pie-chart": PieChartIcon,
  "heart-pulse": Heart,
};

const ACCENT: Record<StatusKind, string> = {
  positive: "from-positive/20 to-transparent border-positive/20",
  neutral: "from-info/20 to-transparent border-info/20",
  attention: "from-attention/20 to-transparent border-attention/20",
  critical: "from-critical/20 to-transparent border-critical/20",
  muted: "from-text-faint/15 to-transparent border-border",
};

const DELTA_COLOR: Record<StatusKind, string> = {
  positive: "text-positive",
  neutral: "text-info",
  attention: "text-attention",
  critical: "text-critical",
  muted: "text-text-muted",
};

interface MetricCardProps {
  label: string;
  value: string;
  delta?: string;
  status: StatusKind;
  icon?: string;
  className?: string;
}

/** Card de KPI "premium" — hero do Dashboard. Faixa de gradiente sutil
 * por status, nunca poluído. */
export function MetricCard({ label, value, delta, status, icon, className }: MetricCardProps) {
  const Icon = icon ? ICONS[icon] : undefined;

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-card border bg-surface p-5 shadow-card",
        "bg-gradient-to-br",
        ACCENT[status],
        className,
      )}
    >
      <div className="flex items-start justify-between">
        <span className="text-sm text-text-muted">{label}</span>
        {Icon && (
          <div className="rounded-lg border border-border-soft bg-surface-hover p-1.5">
            <Icon className="h-4 w-4 text-text-muted" strokeWidth={1.75} />
          </div>
        )}
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight text-text-primary">{value}</div>
      {delta && <div className={cn("mt-1 text-xs font-medium", DELTA_COLOR[status])}>{delta}</div>}
    </div>
  );
}
