import { cn } from "@/lib/utils";
import type { StatusKind } from "@/lib/mock/dashboard";

const STATUS_STYLES: Record<StatusKind, string> = {
  positive: "bg-positive/10 text-positive border-positive/30",
  neutral: "bg-info/10 text-info border-info/30",
  attention: "bg-attention/10 text-attention border-attention/30",
  critical: "bg-critical/10 text-critical border-critical/30",
  muted: "bg-text-faint/10 text-text-muted border-text-faint/30",
};

interface StatusBadgeProps {
  label: string;
  status: StatusKind;
  className?: string;
}

/** Badge de status genérico — a cor sempre vem de uma chave semântica
 * resolvida aqui, nunca calculada pela API (mesma regra do Streamlit). */
export function StatusBadge({ label, status, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        STATUS_STYLES[status],
        className,
      )}
    >
      {label}
    </span>
  );
}

const RISK_LABELS: Record<string, StatusKind> = {
  baixo: "positive",
  moderado: "neutral",
  "moderado-alto": "attention",
  alto: "critical",
  indeterminado: "muted",
};

/** RiskBadge — mesma paleta semântica de risco usada no Streamlit
 * (baixo/moderado/moderado-alto/alto/indeterminado). */
export function RiskBadge({ classification }: { classification: keyof typeof RISK_LABELS | string }) {
  const status = RISK_LABELS[classification] ?? "muted";
  const label = classification.charAt(0).toUpperCase() + classification.slice(1);
  return <StatusBadge label={label} status={status} />;
}
