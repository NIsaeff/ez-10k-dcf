import { AiChat01Icon, Cancel01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react"

import { ChatView } from "@/components/chat/ChatView"
import { sendChat, type ChatMessage } from "@/lib/chat"

const STORAGE_KEY = "ez10k-chat-open"
const WIDTH_KEY = "ez10k-chat-width"
const MIN_WIDTH = 280
const MAX_WIDTH = 680

type ChatPanelState = {
  open: boolean
  setOpen: (open: boolean) => void
  width: number
  setWidth: (width: number) => void
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
  const [width, setWidth] = useState<number>(() => {
    if (typeof localStorage === "undefined") return 380
    const stored = Number(localStorage.getItem(WIDTH_KEY))
    return Number.isFinite(stored) && stored >= MIN_WIDTH ? stored : 380
  })
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [isSending, setIsSending] = useState(false)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(open))
  }, [open])

  useEffect(() => {
    localStorage.setItem(WIDTH_KEY, String(width))
  }, [width])

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
      value={{ open, setOpen, width, setWidth, messages, isSending, send }}
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
  const { open, setOpen, width, setWidth } = useChatPanel()
  const [dragging, setDragging] = useState(false)
  const drag = useRef<{ startX: number; startWidth: number; moved: boolean } | null>(
    null,
  )

  const clampWidth = (value: number) =>
    Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Math.min(value, window.innerWidth * 0.45)))

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId)
    setDragging(true)
    drag.current = {
      startX: event.clientX,
      startWidth: open ? width : 0,
      moved: false,
    }
  }

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const state = drag.current
    if (!state) return
    const delta = state.startX - event.clientX
    if (Math.abs(delta) > 3) state.moved = true
    if (!state.moved) return
    setWidth(clampWidth(state.startWidth + delta))
    if (!open) setOpen(true)
  }

  const endDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const state = drag.current
    drag.current = null
    setDragging(false)
    if (!state) return
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    // A click without movement behaves like the sidebar rail: toggle.
    if (!state.moved) setOpen(!open)
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      setOpen(!open)
    } else if (event.key === "ArrowLeft") {
      event.preventDefault()
      setWidth(clampWidth(width + 24))
    } else if (event.key === "ArrowRight") {
      event.preventDefault()
      setWidth(clampWidth(width - 24))
    }
  }

  return (
    <div className="relative flex shrink-0">
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={open ? "Resize or collapse AI chat" : "Open AI chat"}
        aria-valuenow={open ? Math.round(width) : 0}
        aria-valuemin={MIN_WIDTH}
        aria-valuemax={MAX_WIDTH}
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={onKeyDown}
        className="absolute inset-y-0 -left-2 z-20 w-4 cursor-col-resize touch-none after:absolute after:inset-y-0 after:left-1/2 after:w-[2px] after:-translate-x-1/2 after:bg-transparent hover:after:bg-border focus-visible:after:bg-primary focus-visible:outline-none"
      />

      <div
        data-slot="chat-panel"
        data-state={open ? "open" : "closed"}
        aria-hidden={!open}
        inert={!open}
        style={{ width: open ? width : 0 }}
        className={`shrink-0 overflow-hidden ${
          dragging ? "transition-none" : "transition-[width] duration-200 ease-linear"
        }`}
      >
        <aside
          aria-label="AI chat panel"
          style={{ width }}
          className={`flex h-full flex-col border-l bg-background ${
            dragging ? "" : "transition-transform duration-200 ease-linear"
          } ${open ? "translate-x-0" : "translate-x-full"}`}
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
    </div>
  )
}
