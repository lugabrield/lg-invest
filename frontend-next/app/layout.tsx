import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AppShell } from "@/components/app-shell";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "LG INVEST — Investment Intelligence Platform",
  description: "Plataforma pessoal de inteligência para investimentos.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${inter.variable} dark`}>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
