"use client";

import { forwardRef, useState } from "react";
import type { InputHTMLAttributes } from "react";
import { Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";

/** FormInput — input de texto padrão do design system. Usado em
 * formulários de Configurações e no modal do Dividendos.me. */
export const FormInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { label?: string }>(
  ({ label, className, id, ...props }, ref) => (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="mb-1.5 block text-xs font-medium text-text-muted">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={id}
        className={cn(
          "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-faint",
          "focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20",
          className,
        )}
        {...props}
      />
    </div>
  ),
);
FormInput.displayName = "FormInput";

/** PasswordInput — igual ao FormInput, com toggle de visibilidade.
 * Nunca deve ser conectado a `autoComplete`/storage persistente — ver
 * docs/SECURITY_NOTES.md (credenciais do Dividendos.me nunca ficam
 * salvas no navegador). */
export const PasswordInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { label?: string }>(
  ({ label, className, id, ...props }, ref) => {
    const [visible, setVisible] = useState(false);
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={id} className="mb-1.5 block text-xs font-medium text-text-muted">
            {label}
          </label>
        )}
        <div className="relative">
          <input
            ref={ref}
            id={id}
            type={visible ? "text" : "password"}
            autoComplete="off"
            className={cn(
              "w-full rounded-lg border border-border bg-surface px-3 py-2 pr-9 text-sm text-text-primary placeholder:text-text-faint",
              "focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20",
              className,
            )}
            {...props}
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-faint hover:text-text-muted"
            tabIndex={-1}
          >
            {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </div>
    );
  },
);
PasswordInput.displayName = "PasswordInput";
