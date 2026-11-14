import { createFileRoute, redirect } from "@tanstack/react-router"

import { defaultWizardSearch } from "@/lib/wizard-state"

export const Route = createFileRoute("/")({
  beforeLoad: () => {
    throw redirect({ to: "/wizard", search: defaultWizardSearch() })
  },
})
