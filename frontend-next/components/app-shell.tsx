import type { ReactNode } from "react";
import { Sidebar } from "@/components/sidebar";

/** AppShell — layout global: sidebar fixa + área de conteúdo. Todas as
 * telas (Dashboard, Carteira, Aporte...) renderizam dentro dele. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="px-5 py-6 sm:px-8 sm:py-8 lg:pl-72">
        <div className="mx-auto max-w-7xl">{children}</div>
      </main>
    </div>
  );
}
