if (import.meta.env.DEV) {
  import("react-grab");
}

import { StrictMode } from "react"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { createRoot } from "react-dom/client"

import "./index.css"
import { routeTree } from "./routeTree.gen"
import { ThemeProvider } from "@/components/theme-provider"

const router = createRouter({ routeTree })

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="system" storageKey="ez10k-theme">
      <RouterProvider router={router} />
    </ThemeProvider>
  </StrictMode>,
)
