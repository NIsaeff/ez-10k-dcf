import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useState, type FormEvent } from "react"

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
import { sendChat, type ChatMessage } from "@/lib/chat"
import { perShare } from "@/lib/format"
import { SUPPORTED_TICKERS } from "@/lib/tickers"

const initialMessages: ChatMessage[] = [
  {
    id: "assistant-1",
    role: "assistant",
    content:
      "Ask me to value a company from its latest 10-K — “value KO”, “value AAPL”, “value PWR” — or ask about a macro series such as the 10-year yield, CPI, or GDP.",
  },
]

export function ChatView({ compact = false }: { compact?: boolean }) {
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
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1">
        <MessageScrollerProvider autoScroll>
          <MessageScroller
            className={`h-full w-full ${compact ? "" : "mx-auto max-w-3xl"}`}
          >
            <MessageScrollerViewport>
              <MessageScrollerContent className={compact ? "p-3" : "p-4"}>
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

      <footer className={compact ? "border-t p-2" : "border-t p-4"}>
        <div
          className={`mb-2 flex w-full flex-wrap gap-1.5 ${compact ? "" : "mx-auto max-w-3xl"}`}
        >
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
        <form
          onSubmit={send}
          className={`flex w-full gap-2 ${compact ? "" : "mx-auto max-w-3xl"}`}
        >
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
    </div>
  )
}
