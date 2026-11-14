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
import { sendChat, type ChatMessage } from "@/lib/chat"

const STORAGE_KEY = "ez10k-chat-open"

type ChatPanelState = {
  open: boolean
  setOpen: (open: boolean) => void
  messages: ChatMessage[]
  isSending: boolean
  send: (text: string) => Promise<void>
}

const initialMessages: ChatMessage[] = [
  {
    id: "assistant-1",
    role: "assistant",
    content:
      "Ask me to value a company from its latest 10-K — “value KO”, “value AAPL”, “value PWR” — or ask about a macro series such as the 10-year yield, CPI, or GDP.",
  },
]

const ChatPanelContext = createContext<ChatPanelState | null>(null)

export function ChatPanelProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState<boolean>(() => {
    if (typeof localStorage === "undefined") return true
    return localStorage.getItem(STORAGE_KEY) !== "false"
  })
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [isSending, setIsSending] = useState(false)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(open))
  }, [open])

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isSending) return

    const next: ChatMessage[] = [
      ...messages,
      { id: crypto.randomUUID(), role: "user", content: trimmed },
    ]
    setMessages(next)
    setIsSending(true)

    try {
      const { reply, valuation, trace, sources } = await sendChat(next)
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: reply,
          valuation,
          trace,
          sources,
        },
      ])
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Request failed: ${message}`,
        },
      ])
    } finally {
      setIsSending(false)
    }
  }

  return (
    <ChatPanelContext.Provider
      value={{ open, setOpen, messages, isSending, send }}
    >
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

  return (
    <div
      data-slot="chat-panel"
      data-state={open ? "open" : "closed"}
      aria-hidden={!open}
      inert={!open}
      className={`shrink-0 overflow-hidden transition-[width] duration-200 ease-linear ${
        open ? "w-[380px] max-w-[45vw]" : "w-0"
      }`}
    >
      <aside
        aria-label="AI chat panel"
        className={`flex h-full w-[380px] max-w-[45vw] flex-col border-l bg-background transition-transform duration-200 ease-linear ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
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
    </div>
  )
}
