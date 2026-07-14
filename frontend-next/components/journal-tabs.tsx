"use client";

import { useState } from "react";
import type { AssetSummary, JournalEntryView, ThesisView } from "@/lib/api";
import { JournalDiaryPanel } from "@/components/journal-diary-panel";
import { JournalThesisPanel } from "@/components/journal-thesis-panel";
import { JournalReviewPanel } from "@/components/journal-review-panel";
import { cn } from "@/lib/utils";

interface JournalTabsProps {
  assets: AssetSummary[];
  entries: JournalEntryView[];
  theses: ThesisView[];
}

const TABS = [
  { key: "diary", label: "Diário" },
  { key: "theses", label: "Teses" },
  { key: "reviews", label: "Revisões" },
] as const;

/** JournalTabs — mesmas 3 abas de `pages_impl/journal.py`
 * (`st.tabs(["Diário", "Teses", "Revisões"])`). Dados vêm do servidor
 * (`app/journal/page.tsx`) e cada painel dispara `router.refresh()`
 * após uma mutação, recarregando as props com o estado mais recente. */
export function JournalTabs({ assets, entries, theses }: JournalTabsProps) {
  const [active, setActive] = useState<(typeof TABS)[number]["key"]>("diary");

  return (
    <div>
      <div className="mb-6 flex gap-1.5 border-b border-border-soft">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActive(tab.key)}
            className={cn(
              "border-b-2 px-3.5 py-2 text-sm font-medium transition-colors",
              active === tab.key
                ? "border-primary text-text-primary"
                : "border-transparent text-text-muted hover:text-text-primary",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {active === "diary" && <JournalDiaryPanel assets={assets} entries={entries} />}
      {active === "theses" && <JournalThesisPanel assets={assets} theses={theses} />}
      {active === "reviews" && <JournalReviewPanel theses={theses} />}
    </div>
  );
}
