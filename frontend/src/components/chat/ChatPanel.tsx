import { AiChat01Icon, Cancel01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useLocation, useNavigate, useSearch } from "@tanstack/react-router"
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"

import { ChatView } from "@/components/chat/ChatView"
import { sendChat, type ChatMessage, type Proposal } from "@/lib/chat"
import {
  validateWizardSearch,
  type WizardSearch,
} from "@/lib/wizard-state"

const STORAGE_KEY = "ez10k-chat-open"
const WIDTH_KEY = "ez10k-chat-width"
const MIN_WIDTH = 280
const MAX_WIDTH = 680

export type ProposalEntry = {
  proposal: Proposal
  messageId: string
  status: "pending" | "applied" | "discarded"
}

type Target =
  | { kind: "wizard"; search: WizardSearch }
  | { kind: "filing"; search: { ticker: string; claim?: string } }

type ChatPanelState = {
  open: boolean
  setOpen: (open: boolean) => void
  width: number
  setWidth: (width: number) => void
  messages: ChatMessage[]
  isSending: boolean
  send: (text: string) => Promise<void>
  proposals: ProposalEntry[]
  pending: ProposalEntry[]
  active: ProposalEntry | null
  activeIndex: number
  setActiveIndex: (index: number) => void
  proposalsFor: (messageId: string) => ProposalEntry[]
  changeFor: (key: string) => ProposalEntry["proposal"]["changes"][number] | null
  apply: (entry: ProposalEntry) => void
  discard: (entry: ProposalEntry) => void
  undo: () => void
  redo: () => void
  canUndo: boolean
  canRedo: boolean
}

const initialMessages: ChatMessage[] = [
  {
    id: "assistant-1",
    role: "assistant",
    content:
      "Ask me to value a company from its latest 10-K — “value KO”, “value AAPL”, “value PWR” — or ask about a macro series such as the 10-year yield, CPI, or GDP. I can also propose changes to the wizard; you always confirm them.",
  },
]

const ChatPanelContext = createContext<ChatPanelState | null>(null)

export function ChatPanelProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const rawSearch = useSearch({ strict: false }) as Record<string, unknown>
  const wizard = useMemo(() => validateWizardSearch(rawSearch), [rawSearch])

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
  const [proposals, setProposals] = useState<ProposalEntry[]>([])
  const [activeIndex, setActiveIndexState] = useState(0)
  const [undoStack, setUndoStack] = useState<Target[]>([])
  const [redoStack, setRedoStack] = useState<Target[]>([])

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(open))
  }, [open])

  useEffect(() => {
    localStorage.setItem(WIDTH_KEY, String(width))
  }, [width])

  const context = useMemo(
    () => ({
      ticker: wizard.ticker,
      years: wizard.years,
      terminal: wizard.terminal,
      model: wizard.model,
      wacc: wizard.wacc,
      growth: wizard.growth,
      tax: wizard.tax,
      capex: wizard.capex,
      shares: wizard.shares,
      tab: wizard.tab,
    }),
    [wizard],
  )

  const currentTarget = (): Target =>
    location.pathname.startsWith("/filing")
      ? {
          kind: "filing",
          search: {
            ticker: wizard.ticker,
            claim:
              typeof rawSearch.claim === "string" ? rawSearch.claim : undefined,
          },
        }
      : { kind: "wizard", search: wizard }

  const navigateTo = (target: Target) => {
    if (target.kind === "filing") {
      navigate({
        to: "/filing",
        search: { ticker: target.search.ticker, claim: target.search.claim },
      })
    } else {
      navigate({ to: "/wizard", search: target.search })
    }
  }

  const targetFor = (proposal: Proposal): Target => {
    if (proposal.kind === "navigate") {
      const nav = proposal.navigation
      const ticker = nav?.ticker ?? wizard.ticker
      if (nav?.tab === "filing" || nav?.claim_id) {
        return {
          kind: "filing",
          search: { ticker, claim: nav?.claim_id ?? undefined },
        }
      }
      return {
        kind: "wizard",
        search: {
          ...wizard,
          ticker,
          tab: (nav?.tab as WizardSearch["tab"]) ?? wizard.tab,
        },
      }
    }

    const next: WizardSearch = { ...wizard }
    for (const change of proposal.changes) {
      const value = change.after
      switch (change.key) {
        case "growth":
          next.growth = Number(value)
          break
        case "tax":
          next.tax = Number(value)
          break
        case "capex":
          next.capex = Number(value)
          break
        case "wacc":
          next.wacc = Number(value)
          break
        case "terminal":
          next.terminal = Number(value)
          break
        case "years":
          next.years = Math.round(Number(value))
          break
        case "shares":
          next.shares = Number(value)
          break
        case "model":
          next.model = value === "constant" ? "constant" : "fade"
          break
        default:
          break
      }
    }
    if (proposal.navigation?.tab) {
      next.tab = proposal.navigation.tab as WizardSearch["tab"]
    }
    return { kind: "wizard", search: next }
  }

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
      const { reply, valuation, trace, sources, proposals: returned } =
        await sendChat(next, context)
      const messageId = crypto.randomUUID()
      setMessages((current) => [
        ...current,
        {
          id: messageId,
          role: "assistant",
          content: reply,
          valuation,
          trace,
          sources,
        },
      ])
      if (returned.length > 0) {
        setProposals((current) => [
          ...current,
          ...returned.map((proposal) => ({
            proposal,
            messageId,
            status: "pending" as const,
          })),
        ])
      }
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

  const pending = proposals.filter((entry) => entry.status === "pending")
  const clampedIndex = Math.min(activeIndex, Math.max(0, pending.length - 1))
  const active = pending[clampedIndex] ?? null

  const mark = (entry: ProposalEntry, status: ProposalEntry["status"]) => {
    setProposals((current) =>
      current.map((item) =>
        item.proposal.id === entry.proposal.id ? { ...item, status } : item,
      ),
    )
  }

  const apply = (entry: ProposalEntry) => {
    setUndoStack((stack) => [...stack, currentTarget()])
    setRedoStack([])
    navigateTo(targetFor(entry.proposal))
    mark(entry, "applied")
  }

  const discard = (entry: ProposalEntry) => {
    mark(entry, "discarded")
  }

  const undo = () => {
    const previous = undoStack[undoStack.length - 1]
    if (!previous) return
    setRedoStack((stack) => [...stack, currentTarget()])
    setUndoStack((stack) => stack.slice(0, -1))
    navigateTo(previous)
  }

  const redo = () => {
    const nextTarget = redoStack[redoStack.length - 1]
    if (!nextTarget) return
    setUndoStack((stack) => [...stack, currentTarget()])
    setRedoStack((stack) => stack.slice(0, -1))
    navigateTo(nextTarget)
  }

  const value: ChatPanelState = {
    open,
    setOpen,
    width,
    setWidth,
    messages,
    isSending,
    send,
    proposals,
    pending,
    active,
    activeIndex: clampedIndex,
    setActiveIndex: setActiveIndexState,
    proposalsFor: (messageId) =>
      proposals.filter((entry) => entry.messageId === messageId),
    changeFor: (key) =>
      active?.proposal.changes.find((change) => change.key === key) ?? null,
    apply,
    discard,
    undo,
    redo,
    canUndo: undoStack.length > 0,
    canRedo: redoStack.length > 0,
  }

  return (
    <ChatPanelContext.Provider value={value}>
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
    Math.max(
      MIN_WIDTH,
      Math.min(MAX_WIDTH, Math.min(value, window.innerWidth * 0.45)),
    )

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
