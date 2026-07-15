import { Clock, Puzzle } from "lucide-react";
import type { DividendosMeStatusView } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";

interface DividendosMeStatusCardProps {
  status: DividendosMeStatusView;
}

function formatDateTime(value: string | null): string {
  if (!value) return "Nunca";
  const date = new Date(value);
  return date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

/** DividendosMeStatusCard — mesma seção "Status da integração" do
 * Streamlit (`_render_status`), sem o card "credenciais configuradas"
 * (deixou de fazer sentido: agora a senha é digitada a cada
 * sincronização em vez de vir de `.env`/`st.secrets`). */
export function DividendosMeStatusCard({ status }: DividendosMeStatusCardProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <div className="rounded-card border border-border bg-surface p-4 shadow-card">
        <div className="flex items-center gap-2 text-xs text-text-faint">
          <Puzzle className="h-3.5 w-3.5" strokeWidth={1.75} />
          Playwright disponível
        </div>
        <div className="mt-2">
          <StatusBadge
            label={status.playwright_available ? "Sim" : "Não"}
            status={status.playwright_available ? "positive" : "attention"}
          />
        </div>
      </div>
      <div className="rounded-card border border-border bg-surface p-4 shadow-card">
        <div className="flex items-center gap-2 text-xs text-text-faint">
          <Clock className="h-3.5 w-3.5" strokeWidth={1.75} />
          Última sincronização com sucesso
        </div>
        <div className="mt-2 text-sm font-medium text-text-primary">
          {formatDateTime(status.last_sync_at)}
        </div>
      </div>
    </div>
  );
}
