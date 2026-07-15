"use client";

import { Eye, EyeOff, LogIn } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface DividendosMeCredentialsFormProps {
  email: string;
  password: string;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onTestLogin: () => void;
  testingLogin: boolean;
  loginTested: boolean | null;
  loginError: string | null;
  disabled: boolean;
}

/** DividendosMeCredentialsForm — e-mail/senha do Dividendos.me. Nunca
 * gravado em localStorage/cookie/sessionStorage — só em estado React do
 * componente pai, enquanto esta tela está aberta (ver
 * docs/DIVIDENDOS_ME_FRONT_SYNC.md). Cada ação (testar login, buscar
 * carteira, confirmar) reenvia e-mail/senha no body da própria
 * requisição — não existe "token de sessão" do Dividendos.me. */
export function DividendosMeCredentialsForm({
  email,
  password,
  onEmailChange,
  onPasswordChange,
  onTestLogin,
  testingLogin,
  loginTested,
  loginError,
  disabled,
}: DividendosMeCredentialsFormProps) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="rounded-card border border-border bg-surface p-5 shadow-card">
      <h2 className="mb-1 text-sm font-medium text-text-primary">1. Credenciais do Dividendos.me</h2>
      <p className="mb-3 text-xs text-text-muted">
        Digitadas aqui a cada sincronização — nunca salvas no navegador nem no servidor. Só
        confirmam login/buscam a carteira quando você clica nos botões abaixo.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs text-text-muted">E-mail</label>
          <input
            type="email"
            autoComplete="off"
            value={email}
            onChange={(e) => onEmailChange(e.target.value)}
            disabled={disabled}
            className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-primary disabled:opacity-50"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-muted">Senha</label>
          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              autoComplete="off"
              value={password}
              onChange={(e) => onPasswordChange(e.target.value)}
              disabled={disabled}
              className="w-full rounded-lg border border-border bg-surface px-3 py-1.5 pr-9 text-sm text-text-primary outline-none focus:border-primary disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-text-faint hover:text-text-muted"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff className="h-4 w-4" strokeWidth={1.75} /> : <Eye className="h-4 w-4" strokeWidth={1.75} />}
            </button>
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={onTestLogin}
          disabled={disabled || testingLogin || !email.trim() || !password.trim()}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg border border-border bg-surface-hover px-3.5 py-2 text-sm font-medium text-text-primary transition-opacity hover:opacity-90 disabled:opacity-50",
          )}
        >
          <LogIn className="h-4 w-4" strokeWidth={1.75} />
          {testingLogin ? "Testando..." : "Testar login"}
        </button>
        {loginTested === true && <span className="text-sm text-positive">Login realizado com sucesso.</span>}
        {loginTested === false && loginError && <span className="text-sm text-critical">{loginError}</span>}
      </div>
    </div>
  );
}
