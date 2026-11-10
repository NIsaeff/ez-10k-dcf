import { Moon02Icon, Sun03Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { Button } from "@/components/ui/button"
import { type Theme, useTheme } from "@/components/theme-provider"

const nextTheme: Record<Theme, Theme> = {
  light: "dark",
  dark: "system",
  system: "light",
}

export function ModeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme()

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(nextTheme[theme])}
      aria-label={`Theme: ${theme}. Switch to ${nextTheme[theme]}`}
      title={`Theme: ${theme} — click for ${nextTheme[theme]}`}
    >
      <HugeiconsIcon
        icon={resolvedTheme === "dark" ? Moon02Icon : Sun03Icon}
        strokeWidth={2}
      />
    </Button>
  )
}
