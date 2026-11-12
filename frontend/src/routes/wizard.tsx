import { createFileRoute } from "@tanstack/react-router"

import { ModeToggle } from "@/components/mode-toggle"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { validateWizardSearch } from "@/lib/wizard-state"

export const Route = createFileRoute("/wizard")({
  validateSearch: validateWizardSearch,
  component: WizardPage,
})

function WizardPage() {
  const { ticker, years, terminal, model, wacc } = Route.useSearch()

  return (
    <>
      <header className="flex items-center justify-between gap-3 border-b px-4 py-4">
        <div className="flex min-w-0 items-center gap-2">
          <SidebarTrigger className="-ml-1" />
          <div className="min-w-0">
            <h1 className="text-lg font-semibold">DCF Wizard</h1>
            <p className="text-xs text-muted-foreground">
              Inspect the inputs, then move the assumptions
            </p>
          </div>
        </div>
        <ModeToggle />
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <div className="mx-auto w-full max-w-5xl">
          <p className="text-sm">
            {ticker} · {years}y · terminal {terminal}% · {model} growth
            {wacc === undefined ? "" : ` · WACC override ${wacc}%`}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            FCFF, WACC and DCF panels land in the next phases. The URL above is
            parsed and clamped by <code>validateWizardSearch</code>.
          </p>
        </div>
      </div>
    </>
  )
}
