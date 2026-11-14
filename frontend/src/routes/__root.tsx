import { createRootRoute, Outlet } from "@tanstack/react-router"

import { AppSidebar } from "@/components/app-sidebar"
import { ChatPanel, ChatPanelProvider } from "@/components/chat/ChatPanel"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"

export const Route = createRootRoute({
  component: RootLayout,
})

function RootLayout() {
  return (
    <ChatPanelProvider>
      <TooltipProvider>
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset className="h-svh min-h-0">
            <div className="flex min-h-0 flex-1">
              <div className="flex min-h-0 min-w-0 flex-1 flex-col">
                <Outlet />
              </div>
              <ChatPanel />
            </div>
          </SidebarInset>
        </SidebarProvider>
      </TooltipProvider>
    </ChatPanelProvider>
  )
}
