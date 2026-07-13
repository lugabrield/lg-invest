import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StatusKind } from "@/lib/mock/dashboard";

const ICON = {
  positive: CheckCircle2,
  neutral: Info,
  attention: AlertTriangle,
  critical: XCircle,
  muted: Info,
} as const;

const STYLES: Record<StatusKind, string> = {
  positive: "border-positive/25 bg-positive/[0.06]",
  neutral: "border-info/25 bg-info/[0.06]",
  attention: "border-attention/25 bg-attention/[0.06]",
  critical: "border-critical/25 bg-critical/[0.06]",
  muted: "border-border bg-surface-hover",
};

const ICON_COLOR: Record<StatusKind, string> = {
  positive: "text-positive",
  neutral: "text-info",
  attention: "text-attention",
  critical: "text-critical",
  muted: "text-text-muted",
};

interface AlertCardProps {
  title: string;
  message: string;
  severity: StatusKind;
}

/** AlertCard / DiagnosticCard — bloco de "Pontos fortes / Atenções /
 * Oportunidades / Próximo passo" do Dashboard. */
export function AlertCard({ title, message, severity }: AlertCardProps) {
  const Icon = ICON[severity];
  return (
    <div className={cn("rounded-card border p-4", STYLES[severity])}>
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4", ICON_COLOR[severity])} strokeWidth={1.75} />
        <span className="text-sm font-medium text-text-primary">{title}</span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-text-muted">{message}</p>
    </div>
  );
}

export const DiagnosticCard = AlertCard;
