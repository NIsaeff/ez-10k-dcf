import {
  AiChat01Icon,
  BookOpen01Icon,
  Calculator01Icon,
} from "@hugeicons/core-free-icons"
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

const navItems = [
  { title: "AI Chat", to: "/", icon: AiChat01Icon, exact: true },
  { title: "DCF Wizard", to: "/wizard", icon: Calculator01Icon, exact: false },
  { title: "10-K Analysis", to: "/filing", icon: BookOpen01Icon, exact: false },
] as const

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
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    isActive={matchRoute({ to: item.to, fuzzy: !item.exact }) !== false}
                    tooltip={item.title}
                    render={<Link to={item.to} />}
                  >
                    <HugeiconsIcon icon={item.icon} strokeWidth={2} />
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  )
}
