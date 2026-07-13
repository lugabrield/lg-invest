import { StatusBadge } from "@/components/status-badge";
import type { StatusKind } from "@/lib/mock/dashboard";

interface RecommendationCardProps {
  ticker: string;
  name?: string;
  amount: string;
  weightLabel: string;
  reason: string;
  tag: "already_have" | "new_candidate";
  scoreBadges: { label: string; status: StatusKind }[];
}

/** RecommendationCard — card de ativo recomendado no Aporte v3. Ainda
 * não usado nesta rodada (Dashboard só) — criado agora porque faz parte
 * do design system pedido e será reaproveitado sem mudança na Fase 3,
 * quando `POST /api/recommendations/aporte` estiver pronto. */
export function RecommendationCard({
  ticker,
  name,
  amount,
  weightLabel,
  reason,
  tag,
  scoreBadges,
}: RecommendationCardProps) {
  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-text-primary">{ticker}</span>
            <StatusBadge
              label={tag === "already_have" ? "Já tenho" : "Novo candidato"}
              status={tag === "already_have" ? "positive" : "attention"}
            />
          </div>
          {name && <div className="mt-0.5 text-xs text-text-faint">{name}</div>}
        </div>
        <div className="text-right">
          <div className="font-semibold text-text-primary">{amount}</div>
          <div className="text-xs text-text-muted">{weightLabel} do aporte</div>
        </div>
      </div>
      <p className="mt-3 text-sm text-text-muted">{reason}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {scoreBadges.map((badge) => (
          <StatusBadge key={badge.label} label={badge.label} status={badge.status} />
        ))}
      </div>
    </div>
  );
}
