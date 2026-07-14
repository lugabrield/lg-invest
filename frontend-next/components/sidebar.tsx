"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  BookOpen,
  Compass,
  LayoutDashboard,
  LineChart,
  RefreshCcw,
  Settings,
  Sparkles,
  Wallet,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Mesmos 3 grupos já validados no Streamlit (Sprint 30): Principal,
// Análise, Operação — mantidos aqui para não reaprender a navegação.
// Telas ainda não migradas para o Next.js ficam com `href: "#"` até sua
// própria fase chegar (Fase 4 entrega Dashboard + Aporte + Carteira).
const NAV_GROUPS = [
  {
    label: "Principal",
    items: [
      { label: "Dashboard", icon: LayoutDashboard, href: "/" },
      { label: "Carteira", icon: Wallet, href: "/carteira" },
      { label: "Aporte", icon: BarChart3, href: "/aporte" },
    ],
  },
  {
    label: "Análise",
    items: [
      { label: "Inteligência", icon: Sparkles, href: "#" },
      { label: "Ativos", icon: LineChart, href: "#" },
      { label: "Radar", icon: Compass, href: "#" },
      { label: "Simulação", icon: BarChart3, href: "#" },
      { label: "Journal", icon: BookOpen, href: "#" },
    ],
  },
  {
    label: "Operação",
    items: [
      { label: "Sincronizar Dividendos.me", icon: RefreshCcw, href: "#" },
      { label: "Configurações", icon: Settings, href: "#" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-border-soft bg-surface/60 backdrop-blur-xl lg:flex">
      <div className="flex h-16 items-center gap-2.5 border-b border-border-soft px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-primary shadow-glow">
          <span className="text-sm font-bold text-white">LG</span>
        </div>
        <div>
          <div className="text-sm font-semibold leading-tight text-text-primary">LG INVEST</div>
          <div className="text-[10px] leading-tight text-text-faint">Investment Intelligence</div>
        </div>
      </div>

      <nav className="scrollbar-thin flex-1 space-y-6 overflow-y-auto px-3 py-5">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <div className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-text-faint">
              {group.label}
            </div>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = item.href !== "#" && pathname === item.href;
                return (
                  <Link
                    key={item.label}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
                      active
                        ? "bg-gradient-to-r from-primary/15 to-transparent text-text-primary shadow-[inset_1px_0_0_0_theme(colors.primary.DEFAULT)]"
                        : "text-text-muted hover:bg-surface-hover hover:text-text-primary",
                    )}
                  >
                    <item.icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
                    <span className="truncate">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-border-soft p-4">
        <div className="flex items-center gap-2.5 rounded-lg bg-surface-hover px-3 py-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-primary text-xs font-semibold text-white">
            LC
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-medium text-text-primary">Lucas Lins</div>
            <div className="truncate text-[10px] text-text-faint">v1.1.0-dev · Local</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
