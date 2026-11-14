import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { createFileRoute } from "@tanstack/react-router"
import { useState, type FormEvent } from "react"

import { ModeToggle } from "@/components/mode-toggle"
import { ChatSources, ChatTrace } from "@/components/ChatTrace"
import { Markdown } from "@/components/Markdown"
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
import { SidebarTrigger } from "@/components/ui/sidebar"
import { sendChat, type ChatMessage } from "@/lib/chat"
import { perShare } from "@/lib/format"
import { SUPPORTED_TICKERS } from "@/lib/tickers"

export const Route = createFileRoute("/")({
  component: ChatPage,
})

const initialMessages: ChatMessage[] = [
  {
    id: "assistant-1",
    role: "assistant",
    content:
      "Ask me to value a company from its latest 10-K — “value KO”, “value AAPL”, “value PWR” — or ask about a macro series such as the 10-year yield, CPI, or GDP.",
  },
]

function ChatPage() {
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
    <>
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
                          <ChatTrace trace={message.trace} />
                          <Bubble
                            align={isUser ? "end" : "start"}
                            variant={isUser ? "default" : "muted"}
                          >
                            <BubbleContent>
                            {isUser ? (
                              message.content
                            ) : (
                              <Markdown text={message.content} />
                            )}
                          </BubbleContent>
                          </Bubble>
                          {message.valuation ? (
                            <a
                              href={`/wizard?ticker=${encodeURIComponent(message.valuation.ticker)}`}
                              className="mt-2 inline-flex items-center gap-2 rounded-lg border border-border/60 bg-card px-3 py-2 text-xs shadow-sm transition-colors hover:bg-muted"
                            >
                              <span className="font-semibold">
                                {message.valuation.ticker}
                              </span>
                              <span className="tabular-nums text-muted-foreground">
                                {perShare(
                                  message.valuation.valuation.value_per_share,
                                )}{" "}
                                / share
                              </span>
                              <span className="flex items-center gap-1 font-medium">
                                Open in DCF Wizard
                                <HugeiconsIcon
                                  icon={ArrowUpRight01Icon}
                                  strokeWidth={2}
                                  className="size-3"
                                />
                              </span>
                            </a>
                          ) : null}
                          <ChatSources sources={message.sources} />
                        </MessageContent>
                      </Message>
                    </MessageScrollerItem>
                  )
                })}
                {isSending ? (
                  <MessageScrollerItem messageId="pending-thinking">
                    <Message align="start">
                      <MessageContent>
                        <ChatTrace running />
                      </MessageContent>
                    </Message>
                  </MessageScrollerItem>
                ) : null}
              </MessageScrollerContent>
            </MessageScrollerViewport>
            <MessageScrollerButton />
          </MessageScroller>
        </MessageScrollerProvider>
      </div>

      <footer className="border-t p-4">
        <div className="mx-auto mb-2 flex w-full max-w-3xl flex-wrap gap-1.5">
          {SUPPORTED_TICKERS.map((ticker) => (
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
            placeholder="value KO — or ask about the 10Y yield"
            aria-label="Message"
            disabled={isSending}
          />
          <Button type="submit" disabled={isSending || !draft.trim()}>
            {isSending ? "Thinking…" : "Send"}
          </Button>
        </form>
      </footer>
    </>
  )
}
