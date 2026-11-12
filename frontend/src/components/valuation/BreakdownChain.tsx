export type ChainLine = {
  op: string
  label: string
  hint?: string
  value: string
  emphasis?: boolean
  /** Draw a rule above this line to close a section. */
  divider?: boolean
}

export function ChainRow({ line }: { line: ChainLine }) {
  return (
    <div className={line.divider ? "mt-1 border-t border-border/60 pt-1" : ""}>
      <div className="flex items-baseline gap-2 py-1">
        <span className="w-3 shrink-0 text-muted-foreground">{line.op}</span>
        <span
          className={line.emphasis ? "font-semibold" : "text-muted-foreground"}
        >
          {line.label}
          {line.hint ? (
            <span className="ml-1 text-[10px] text-muted-foreground/80">
              ({line.hint})
            </span>
          ) : null}
        </span>
        <span
          className={`ml-auto tabular-nums ${line.emphasis ? "font-semibold" : ""}`}
        >
          {line.value}
        </span>
      </div>
    </div>
  )
}

export function BreakdownChain({
  lines,
  title = "How this adds up",
}: {
  lines: ChainLine[]
  title?: string
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <div className="mt-1 text-xs">
        {lines.map((line) => (
          <ChainRow key={`${line.op}-${line.label}`} line={line} />
        ))}
      </div>
    </div>
  )
}
