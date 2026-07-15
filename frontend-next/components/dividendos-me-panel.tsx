"use client";

import { useState } from "react";
import { Info } from "lucide-react";
import type { DividendosMeStatusView } from "@/lib/api";
import { ApiError, testDividendosMeLogin } from "@/lib/api";
import { DividendosMeCredentialsForm } from "@/components/dividendos-me-credentials-form";
import { DividendosMeSyncSection } from "@/components/dividendos-me-sync-section";
import { DividendosMeIncomeMonthlySection } from "@/components/dividendos-me-income-monthly-section";
import { DividendosMeIncomeCalendarSection } from "@/components/dividendos-me-income-calendar-section";
import { AlertCard } from "@/components/alert-card";

interface DividendosMePanelProps {
  status: DividendosMeStatusView;
  portfolioId: number;
}

/** DividendosMePanel — orquestra a tela inteira: credenciais ficam só em
 * estado React deste componente (nunca em localStorage/cookie, nunca
 * enviadas para nenhum outro domínio além da própria API da LG
 * INVEST), e são repassadas para cada seção como props — cada seção
 * dispara sua própria chamada HTTP independente, reenviando
 * e-mail/senha a cada ação (ver docs/DIVIDENDOS_ME_FRONT_SYNC.md). Sair
 * desta tela (trocar de rota) descarta o estado automaticamente. */
export function DividendosMePanel({ status, portfolioId }: DividendosMePanelProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [testingLogin, setTestingLogin] = useState(false);
  const [loginTested, setLoginTested] = useState<boolean | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);

  const buttonsDisabled = !status.playwright_available;

  async function handleTestLogin() {
    setTestingLogin(true);
    setLoginError(null);
    try {
      await testDividendosMeLogin({ email, password });
      setLoginTested(true);
    } catch (err) {
      setLoginTested(false);
      setLoginError(
        err instanceof ApiError ? err.message : "Falha inesperada ao testar login. Tente novamente em alguns instantes.",
      );
    } finally {
      setTestingLogin(false);
    }
  }

  return (
    <div className="space-y-6">
      {!status.playwright_available && (
        <AlertCard
          title="Playwright indisponível neste ambiente"
          message={`A sincronização com o Dividendos.me só funciona rodando localmente — use "python -m scripts.sync_dividendos_me --portfolio-id ${portfolioId} --mode dry-run" no seu computador, ou rode a API em um ambiente com Playwright instalado.`}
          severity="attention"
        />
      )}

      <DividendosMeCredentialsForm
        email={email}
        password={password}
        onEmailChange={(value) => {
          setEmail(value);
          setLoginTested(null);
        }}
        onPasswordChange={(value) => {
          setPassword(value);
          setLoginTested(null);
        }}
        onTestLogin={handleTestLogin}
        testingLogin={testingLogin}
        loginTested={loginTested}
        loginError={loginError}
        disabled={buttonsDisabled}
      />

      <DividendosMeSyncSection
        credentials={{ email, password }}
        portfolioId={portfolioId}
        disabled={buttonsDisabled || !email.trim() || !password.trim()}
      />

      <div className="border-t border-border-soft pt-6">
        <DividendosMeIncomeMonthlySection
          credentials={{ email, password }}
          portfolioId={portfolioId}
          disabled={buttonsDisabled || !email.trim() || !password.trim()}
        />
      </div>

      <div>
        <div className="rounded-card border border-border bg-surface p-5 shadow-card">
          <h2 className="mb-1 text-sm font-medium text-text-primary">5C. Proventos — Por ativo/mês</h2>
          <div className="flex items-start gap-2 text-sm text-text-muted">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" strokeWidth={1.75} />
            <p>
              Fonte detectada, extração ainda não disponível. O Dividendos.me tem uma tela (&quot;Renda
              Variável → Brasil → Gráficos → Dividendos por Ativo&quot;) que mostra o total de
              proventos por classe/ativo/mês num gráfico empilhado, mas os dados vivem dentro de um
              gráfico (Highcharts/ApexCharts), não numa tabela HTML simples como as outras fontes
              desta tela. A LG INVEST não grava nem estima renda por ativo/mês até que isso seja
              validado contra dado real — só o agregado mensal por carteira e o calendário futuro por
              ativo.
            </p>
          </div>
        </div>
      </div>

      <div className="border-t border-border-soft pt-6">
        <DividendosMeIncomeCalendarSection
          credentials={{ email, password }}
          portfolioId={portfolioId}
          disabled={buttonsDisabled || !email.trim() || !password.trim()}
        />
      </div>
    </div>
  );
}
