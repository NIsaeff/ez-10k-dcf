import type { SourceFact } from "@/lib/chat"
import { metricLabel } from "@/lib/fact-labels"
import { compact, shareCount } from "@/lib/format"

function FactValue({ fact }: { fact: SourceFact }) {
  return fact.unit === "shares" ? shareCount(fact.value) : compact(fact.value)
}

type FactGroup = { metric: string; label: string; facts: SourceFact[] }

function groupFacts(facts: SourceFact[]): FactGroup[] {
  const order: string[] = []
  const byMetric = new Map<string, SourceFact[]>()

  for (const fact of facts) {
    if (!byMetric.has(fact.metric)) {
      byMetric.set(fact.metric, [])
      order.push(fact.metric)
    }
    byMetric.get(fact.metric)?.push(fact)
  }

  return order.map((metric) => ({
    metric,
    label: metricLabel(metric),
    facts: byMetric.get(metric) ?? [],
  }))
}

export function FactTable({ facts }: { facts: SourceFact[] }) {
  const groups = groupFacts(facts)
  if (groups.length === 0) return null

  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        XBRL inputs ({facts.length} facts)
      </p>
      <div className="mt-1 divide-y divide-border/40 border-y border-border/40">
        {groups.map((group) => (
          <details key={group.metric} className="group">
            <summary className="flex cursor-pointer list-none items-center gap-2 py-1.5 text-xs hover:text-foreground">
              <span className="w-3 shrink-0 text-muted-foreground transition-transform group-open:rotate-90">
                ▸
              </span>
              <span className="shrink-0 font-medium">{group.label}</span>
              <span className="min-w-0 flex-1 truncate font-mono text-[10px] text-muted-foreground">
                {Array.from(new Set(group.facts.map((fact) => fact.tag))).join(
                  ", ",
                )}
              </span>
              <span className="shrink-0 text-[10px] text-muted-foreground">
                {group.facts.length}
              </span>
            </summary>
            <div className="pb-2 pl-5">
              <table className="w-full text-left text-[11px]">
                <thead className="text-muted-foreground">
                  <tr>
                    <th className="py-0.5 pr-3 font-medium">FY</th>
                    <th className="py-0.5 pr-3 font-medium">Tag</th>
                    <th className="py-0.5 pr-3 font-medium">Value</th>
                    <th className="py-0.5 pr-3 font-medium">Filed / period</th>
                    <th className="py-0.5 font-medium">Source</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {group.facts.map((fact) => (
                    <tr
                      key={`${fact.metric}-${fact.tag}-${fact.fiscal_year}`}
                      className="border-t border-border/30"
                    >
                      <td className="py-0.5 pr-3">{fact.fiscal_year}</td>
                      <td className="max-w-[10rem] truncate py-0.5 pr-3 font-mono text-[10px] text-muted-foreground">
                        {fact.tag}
                      </td>
                      <td className="py-0.5 pr-3">
                        <FactValue fact={fact} />
                      </td>
                      <td className="py-0.5 pr-3 text-muted-foreground">
                        {fact.filed ?? "—"}
                        {fact.end ? ` · ${fact.end}` : ""}
                      </td>
                      <td className="py-0.5">
                        <a
                          href={fact.url}
                          target="_blank"
                          rel="noreferrer"
                          className="underline underline-offset-2 hover:text-foreground"
                        >
                          {fact.accession_number ?? "SEC filing"}
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        ))}
      </div>
    </div>
  )
}
