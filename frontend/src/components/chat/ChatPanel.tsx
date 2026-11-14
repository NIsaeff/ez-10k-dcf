import { AiChat01Icon, Cancel01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"

import { ChatView } from "@/components/chat/ChatView"

const STORAGE_KEY = "ez10k-chat-open"

type ChatPanelState = {
  open: boolean
  setOpen: (open: boolean) => void
}

const ChatPanelContext = createContext<ChatPanelState | null>(null)

export function ChatPanelProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState<boolean>(() => {
    if (typeof localStorage === "undefined") return true
    return localStorage.getItem(STORAGE_KEY) !== "false"
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(open))
  }, [open])

  return (
    <ChatPanelContext.Provider value={{ open, setOpen }}>
      {children}
    </ChatPanelContext.Provider>
  )
}

export function useChatPanel(): ChatPanelState {
  const value = useContext(ChatPanelContext)
  if (!value) {
    throw new Error("useChatPanel must be used inside ChatPanelProvider")
  }
  return value
}

export function ChatToggle() {
  const { open, setOpen } = useChatPanel()

  return (
    <button
      type="button"
      onClick={() => setOpen(!open)}
      aria-label={open ? "Hide AI chat" : "Show AI chat"}
      aria-pressed={open}
      title={open ? "Hide AI chat" : "Show AI chat"}
      className={`rounded-md border p-1.5 transition-colors ${
        open
          ? "border-primary/40 bg-primary/10 text-foreground"
          : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
    >
      <HugeiconsIcon icon={AiChat01Icon} strokeWidth={2} className="size-4" />
    </button>
  )
}

export function ChatPanel() {
  const { open, setOpen } = useChatPanel()
  if (!open) return null

  return (
    <aside
      aria-label="AI chat panel"
      className="flex w-[380px] max-w-[45vw] shrink-0 flex-col border-l bg-background"
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <HugeiconsIcon
            icon={AiChat01Icon}
            strokeWidth={2}
            className="size-4 text-muted-foreground"
          />
          <span className="text-sm font-semibold">AI Chat</span>
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label="Close AI chat"
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <HugeiconsIcon icon={Cancel01Icon} strokeWidth={2} className="size-4" />
        </button>
      </div>
      <ChatView compact />
    </aside>
  )
}
