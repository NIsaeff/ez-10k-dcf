import type { ProjectionYear, YearFinancials } from "@/lib/chat"
import { compact } from "@/lib/format"

type Bar = { year: number; value: number; projected: boolean }

export function FcffChart({
  history,
  projection,
}: {
  history: YearFinancials[]
  projection: ProjectionYear[]
}) {
  const bars: Bar[] = [
    ...history.map((year) => ({
      year: year.fiscal_year,
      value: year.fcff,
      projected: false,
    })),
    ...projection.map((year) => ({
      year: year.year,
      value: year.fcff,
      projected: true,
    })),
  ]

  if (bars.length === 0) return null

  const values = bars.map((bar) => bar.value)
  const max = Math.max(0, ...values)
  const min = Math.min(0, ...values)
  const span = max - min || 1

  const width = 640
  const height = 170
  const padding = { top: 10, right: 8, bottom: 22, left: 8 }
  const plotHeight = height - padding.top - padding.bottom
  const slot = (width - padding.left - padding.right) / bars.length
  const barWidth = Math.max(4, slot * 0.62)
  const zeroY = padding.top + (max / span) * plotHeight

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      role="img"
      aria-label="FCFF by fiscal year, history and projection"
    >
      <line
        x1={padding.left}
        x2={width - padding.right}
        y1={zeroY}
        y2={zeroY}
        className="stroke-border"
        strokeWidth={1}
      />
      {bars.map((bar, index) => {
        const x = padding.left + index * slot + (slot - barWidth) / 2
        const magnitude = (Math.abs(bar.value) / span) * plotHeight
        const y = bar.value >= 0 ? zeroY - magnitude : zeroY
        return (
          <g key={bar.year}>
            <rect
              x={x}
              y={y}
              width={barWidth}
              height={Math.max(1, magnitude)}
              rx={2}
              className={
                bar.value < 0
                  ? "fill-destructive stroke-destructive"
                  : bar.projected
                    ? "fill-primary stroke-primary"
                    : "fill-muted-foreground stroke-muted-foreground"
              }
              strokeWidth={bar.projected ? 1 : 0}
              strokeDasharray={bar.projected ? "3 2" : undefined}
              opacity={bar.projected ? 0.85 : bar.value < 0 ? 0.6 : 0.5}
            />
            <text
              x={x + barWidth / 2}
              y={height - 8}
              textAnchor="middle"
              className="fill-muted-foreground"
              fontSize={9}
            >
              {String(bar.year).slice(2)}
            </text>
            <title>{`FY${bar.year} · ${compact(bar.value)}${bar.projected ? " (projected)" : ""}`}</title>
          </g>
        )
      })}
    </svg>
  )
}
