"use client";

import type { ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

/** Modal — base para o fluxo de credenciais do Dividendos.me (Fase 6) e
 * qualquer outro diálogo. Fecha ao clicar fora ou no X; nunca guarda
 * estado sensível fora do próprio componente que a instancia. */
export function Modal({ open, onClose, title, children }: ModalProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div role="dialog" aria-modal="true" className="w-full max-w-md rounded-card border border-border bg-surface p-6 shadow-card">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">{title}</h2>
          <button onClick={onClose} className="text-text-faint hover:text-text-primary">
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

interface ConfirmDialogProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  destructive?: boolean;
}

/** ConfirmDialog — confirmação simples (update) ou pode ser combinado
 * com FormInput para a confirmação forte por frase digitada (replace do
 * Dividendos.me — ver docs/DIVIDENDOS_ME_FRONT_SYNC.md). */
export function ConfirmDialog({
  open,
  onCancel,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirmar",
  destructive = false,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} onClose={onCancel} title={title}>
      <p className="text-sm text-text-muted">{message}</p>
      <div className="mt-5 flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="rounded-lg border border-border px-3.5 py-2 text-sm font-medium text-text-muted hover:bg-surface-hover"
        >
          Cancelar
        </button>
        <button
          onClick={onConfirm}
          className={cn(
            "rounded-lg px-3.5 py-2 text-sm font-medium text-white",
            destructive ? "bg-critical hover:opacity-90" : "bg-gradient-primary shadow-glow hover:opacity-90",
          )}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
