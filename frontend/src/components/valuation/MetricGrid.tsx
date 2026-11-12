export type MetricItem = {
  label: string
  value: string | null
  hint?: string
}

export function Metric({
  label,
  value,
  hint,
}: {
  label: string
  value: string | null
  hint?: string
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-muted/30 p-2.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums">{value ?? "—"}</p>
      {hint ? (
        <p className="mt-0.5 text-[10px] text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  )
}

export function MetricGrid({
  items,
  columns = 4,
}: {
  items: MetricItem[]
  columns?: 2 | 3 | 4
}) {
  const columnClass =
    columns === 2
      ? "sm:grid-cols-2"
      : columns === 3
        ? "sm:grid-cols-3"
        : "sm:grid-cols-4"

  return (
    <div className={`grid grid-cols-2 gap-2 ${columnClass}`}>
      {items.map((item) => (
        <Metric
          key={item.label}
          label={item.label}
          value={item.value}
          hint={item.hint}
        />
      ))}
    </div>
  )
}
