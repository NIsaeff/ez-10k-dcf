import { useState, type FormEvent } from "react"

import { AppSidebar } from "@/components/app-sidebar"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Message, MessageContent } from "@/components/ui/message"
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { ModeToggle } from "@/components/mode-toggle"
import { ValuationCard } from "@/components/ValuationCard"
import { sendChat, type ChatMessage } from "@/lib/chat"

const TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "KO", "PWR"]

const initialMessages: ChatMessage[] = [
  {
    id: "assistant-1",
    role: "assistant",
    content:
      "Ask me to value a company from its latest 10-K. Try “value KO”, “value AAPL”, or “value PWR”.",
  },
]

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [draft, setDraft] = useState("")
  const [isSending, setIsSending] = useState(false)

  const send = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const text = draft.trim()
    if (!text || isSending) return

    const next: ChatMessage[] = [
      ...messages,
      { id: crypto.randomUUID(), role: "user", content: text },
    ]
    setMessages(next)
    setDraft("")
    setIsSending(true)

    try {
      const { reply, valuation } = await sendChat(next)
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: reply,
          valuation,
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
    <TooltipProvider>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset className="h-svh min-h-0">
          <header className="flex items-center justify-between gap-3 border-b px-4 py-4">
            <div className="flex min-w-0 items-center gap-2">
              <SidebarTrigger className="-ml-1" />
              <div className="min-w-0">
                <h1 className="text-lg font-semibold">EZ-10k: Agentic DCF</h1>
                <p className="text-xs text-muted-foreground">
                  SEC 10-K financials → FCFF → DCF valuation
                </p>
              </div>
            </div>
            <ModeToggle />
          </header>

          <div className="min-h-0 flex-1">
            <MessageScrollerProvider autoScroll>
              <MessageScroller className="mx-auto h-full w-full max-w-3xl">
                <MessageScrollerViewport>
                  <MessageScrollerContent className="p-4">
                    {messages.map((message, index) => {
                      const isUser = message.role === "user"

                      return (
                        <MessageScrollerItem
                          key={message.id}
                          messageId={message.id}
                          scrollAnchor={index === messages.length - 1}
                        >
                          <Message align={isUser ? "end" : "start"}>
                            <MessageContent>
                              <Bubble
                                align={isUser ? "end" : "start"}
                                variant={isUser ? "default" : "muted"}
                              >
                                <BubbleContent>{message.content}</BubbleContent>
                              </Bubble>
                              {message.valuation ? (
                                <ValuationCard valuation={message.valuation} />
                              ) : null}
                            </MessageContent>
                          </Message>
                        </MessageScrollerItem>
                      )
                    })}
                  </MessageScrollerContent>
                </MessageScrollerViewport>
                <MessageScrollerButton />
              </MessageScroller>
            </MessageScrollerProvider>
          </div>

          <footer className="border-t p-4">
            <div className="mx-auto mb-2 flex w-full max-w-3xl flex-wrap gap-1.5">
              {TICKERS.map((ticker) => (
                <button
                  key={ticker}
                  type="button"
                  onClick={() => setDraft(`value ${ticker}`)}
                  disabled={isSending}
                  className="rounded-full border border-border/60 px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
                >
                  {ticker}
                </button>
              ))}
            </div>
            <form onSubmit={send} className="mx-auto flex w-full max-w-3xl gap-2">
              <Input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="value KO"
                aria-label="Message"
                disabled={isSending}
              />
              <Button type="submit" disabled={isSending || !draft.trim()}>
                {isSending ? "Valuing…" : "Send"}
              </Button>
            </form>
          </footer>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}
