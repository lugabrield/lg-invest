import Link from "next/link";
import type { AssetRowView } from "@/lib/api";
import { PRICE_STATUS_LABELS } from "@/lib/adapt-ativos";

// Tabela de ativos cadastrados — Fase 6. Espelha a tabela de
// `pages_impl/ativos.py` (ticker, nome, classe, país, moeda, setor,
// preço, status do preço, atualizado em), com link para o detalhe.
export function AssetListTable({ rows }: { rows: AssetRowView[] }) {
  const missing = rows.filter((r) => r.price_status === "missing");

  return (
    <div>
      <div className="rounded-card border border-border bg-surface shadow-card">
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-soft text-left text-xs text-text-faint">
                <th className="px-5 py-2.5 font-medium">Ticker</th>
                <th className="px-5 py-2.5 font-medium">Nome</th>
                <th className="px-5 py-2.5 font-medium">Classe</th>
                <th className="px-5 py-2.5 font-medium">Setor</th>
                <th className="px-5 py-2.5 text-right font-medium">Preço atual</th>
                <th className="px-5 py-2.5 font-medium">Status</th>
                <th className="px-5 py-2.5 font-medium">Atualizado em</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.ticker} className="border-b border-border-soft/60 last:border-0">
                  <td className="px-5 py-3">
                    <Link href={`/ativos/${encodeURIComponent(row.ticker)}`} className="font-medium text-primary hover:underline">
                      {row.ticker}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-text-muted">{row.name}</td>
                  <td className="px-5 py-3 text-text-muted">
                    {row.asset_class} · {row.currency}
                  </td>
                  <td className="px-5 py-3 text-text-muted">{row.sector ?? "—"}</td>
                  <td className="px-5 py-3 text-right text-text-primary">{row.price ?? "—"}</td>
                  <td className="px-5 py-3 text-text-muted">{PRICE_STATUS_LABELS[row.price_status]}</td>
                  <td className="px-5 py-3 text-text-faint">
                    {row.updated_at ? new Date(row.updated_at).toLocaleString("pt-BR") : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {missing.length > 0 && (
        <p className="mt-2 text-xs text-attention">
          Sem nenhum preço cadastrado ainda: {missing.map((r) => r.ticker).join(", ")}.
        </p>
      )}
    </div>
  );
}
