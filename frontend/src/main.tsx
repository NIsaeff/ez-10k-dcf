if (import.meta.env.DEV) {
  import("react-grab");
}

import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import App from "./App"
import { ThemeProvider } from "@/components/theme-provider"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider defaultTheme="system" storageKey="ez10k-theme">
      <App />
    </ThemeProvider>
  </StrictMode>,
)
