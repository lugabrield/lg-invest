import { RefreshCcw, Sparkles } from "lucide-react";

interface TopBarProps {
  greeting: string;
  lastUpdated: string;
}

/** TopBar — saudação + última atualização + ações principais (atualizar
 * dados / simular aporte). Fica dentro do AppShell, ao lado da Sidebar. */
export function TopBar({ greeting, lastUpdated }: TopBarProps) {
  return (
    <div className="flex flex-col gap-4 border-b border-border-soft pb-6 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-text-primary">{greeting}</h1>
        <p className="mt-1 text-sm text-text-muted">Última atualização {lastUpdated}</p>
      </div>
      <div className="flex items-center gap-2">
        <button className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover">
          <RefreshCcw className="h-4 w-4" strokeWidth={1.75} />
          Atualizar dados
        </button>
        <button className="inline-flex items-center gap-2 rounded-lg bg-gradient-primary px-3.5 py-2 text-sm font-medium text-white shadow-glow transition-opacity hover:opacity-90">
          <Sparkles className="h-4 w-4" strokeWidth={1.75} />
          Simular aporte
        </button>
      </div>
    </div>
  );
}
