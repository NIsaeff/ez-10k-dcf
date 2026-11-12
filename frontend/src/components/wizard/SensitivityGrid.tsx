import type { SensitivityGrid as Grid } from "@/lib/api"
import { perShare, pct } from "@/lib/format"

export function SensitivityGrid({
  grid,
  currentWacc,
  currentTerminal,
}: {
  grid: Grid
  currentWacc: number
  currentTerminal: number
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[30rem] text-left text-xs">
        <thead className="text-muted-foreground">
          <tr>
            <th className="py-1.5 pr-3 font-medium">
              WACC ↓ / terminal growth →
            </th>
            {grid.growth_values.map((growth) => (
              <th
                key={growth}
                className={`py-1.5 pr-3 text-right font-medium tabular-nums ${
                  Math.abs(growth - currentTerminal) < 1e-9 ? "text-foreground" : ""
                }`}
              >
                {pct(growth)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {grid.values.map((row, rowIndex) => {
            const wacc = grid.wacc_values[rowIndex] ?? 0
            const isCurrentWacc = Math.abs(wacc - currentWacc) < 1e-9
            return (
              <tr key={wacc} className="border-t border-border/40">
                <td
                  className={`py-1.5 pr-3 font-medium ${
                    isCurrentWacc ? "text-foreground" : "text-muted-foreground"
                  }`}
                >
                  {pct(wacc)}
                </td>
                {row.map((value, columnIndex) => {
                  const growth = grid.growth_values[columnIndex] ?? 0
                  const isBase =
                    isCurrentWacc && Math.abs(growth - currentTerminal) < 1e-9
                  return (
                    <td
                      key={`${wacc}-${growth}`}
                      className={`py-1.5 pr-3 text-right ${
                        isBase
                          ? "rounded bg-primary/10 font-semibold text-foreground"
                          : value === null
                            ? "text-muted-foreground/50"
                            : ""
                      }`}
                    >
                      {value === null ? "—" : perShare(value)}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
