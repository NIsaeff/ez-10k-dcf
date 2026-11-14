import { BookOpen01Icon, Calculator01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { Link, useMatchRoute } from "@tanstack/react-router"

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import { defaultWizardSearch } from "@/lib/wizard-state"

export function AppSidebar() {
  const matchRoute = useMatchRoute()

  return (
    <Sidebar>
      <SidebarHeader>
        <div className="flex items-baseline gap-2 px-2 py-1.5">
          <span className="text-sm font-semibold">EZ-10k</span>
          <span className="text-[10px] text-muted-foreground">Agentic DCF</span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={matchRoute({ to: "/wizard" }) !== false}
                  tooltip="DCF Wizard"
                  render={
                    <Link to="/wizard" search={defaultWizardSearch()} />
                  }
                >
                  <HugeiconsIcon icon={Calculator01Icon} strokeWidth={2} />
                  <span>DCF Wizard</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={matchRoute({ to: "/filing" }) !== false}
                  tooltip="10-K Analysis"
                  render={
                    <Link
                      to="/filing"
                      search={{ ticker: "KO", claim: undefined }}
                    />
                  }
                >
                  <HugeiconsIcon icon={BookOpen01Icon} strokeWidth={2} />
                  <span>10-K Analysis</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
