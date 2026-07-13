import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Combina classes Tailwind com merge de conflitos — utilitário padrão shadcn/ui. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
