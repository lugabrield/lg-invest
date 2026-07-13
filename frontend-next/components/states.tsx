import type { ReactNode } from "react";
import { AlertCircle, Inbox } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  message: string;
  action?: ReactNode;
  className?: string;
}

/** EmptyState — tela ou seção sem dado ainda, com CTA opcional (mesma
 * ideia do `empty_state()` do Streamlit, agora em React). */
export function EmptyState({ icon, title, message, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-card border border-dashed border-border bg-surface/50 px-6 py-12 text-center",
        className,
      )}
    >
      <div className="mb-3 text-text-faint">{icon ?? <Inbox className="h-8 w-8" strokeWidth={1.5} />}</div>
      <div className="text-sm font-medium text-text-primary">{title}</div>
      <p className="mt-1.5 max-w-sm text-sm text-text-muted">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** ErrorState — falha ao carregar dado da API; nunca mostra stack trace. */
export function ErrorState({ message = "Não foi possível carregar os dados agora. Tente novamente." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-card border border-critical/25 bg-critical/[0.06] px-6 py-12 text-center">
      <AlertCircle className="mb-3 h-8 w-8 text-critical" strokeWidth={1.5} />
      <p className="max-w-sm text-sm text-text-muted">{message}</p>
    </div>
  );
}

/** LoadingSkeleton — placeholder de carregamento para cards/gráficos. */
export function LoadingSkeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-card bg-surface-hover", className)} />;
}
