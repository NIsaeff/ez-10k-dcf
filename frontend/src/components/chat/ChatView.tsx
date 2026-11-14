import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useState, type FormEvent } from "react"

import { ChatSources, ChatTrace } from "@/components/ChatTrace"
import { ProposalCard, ProposalQueue } from "@/components/chat/ProposalCard"
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
import { useChatPanel } from "@/components/chat/ChatPanel"
import { perShare } from "@/lib/format"
import { SUPPORTED_TICKERS } from "@/lib/tickers"

const MACRO_SERIES = [
  { id: "DGS10", label: "10Y Treasury yield" },
  { id: "DFF", label: "Fed funds rate" },
  { id: "CPIAUCSL", label: "CPI (inflation)" },
  { id: "UNRATE", label: "Unemployment rate" },
  { id: "GDPC1", label: "Real GDP" },
  { id: "UMCSENT", label: "Consumer sentiment" },
]

export function ChatView({ compact = false }: { compact?: boolean }) {
  const { messages, isSending, send, proposalsFor } = useChatPanel()
  const [draft, setDraft] = useState("")
  const [series, setSeries] = useState<Set<string>>(new Set())

  const toggleSeries = (id: string) => {
    setSeries((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const askFred = () => {
    if (series.size === 0 || isSending) return
    const picked = MACRO_SERIES.filter((item) => series.has(item.id)).map(
      (item) => `${item.id} (${item.label})`,
    )
    setSeries(new Set())
    void send(
      `Using FRED, pull the latest value for each of: ${picked.join(", ")}. ` +
        "Give the series ID, units and observation date for each.",
    )
  }

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const text = draft.trim()
    if (!text || isSending) return
    setDraft("")
    void send(text)
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
                          {proposalsFor(message.id).map((entry) => (
                            <ProposalCard key={entry.proposal.id} entry={entry} />
                          ))}
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
          className={`mb-2 flex w-full items-start justify-between gap-2 ${compact ? "" : "mx-auto max-w-3xl"}`}
        >
          <details className="group relative min-w-0">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-full border border-border/60 px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
              <span className="transition-transform group-open:rotate-90">▸</span>
              Example Stocks
            </summary>
            <div className="absolute bottom-full left-0 z-30 mb-2 flex w-60 flex-wrap gap-1.5 rounded-lg border bg-popover p-2 shadow-lg">
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
          </details>

          <details className="group relative min-w-0">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-full border border-border/60 px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
              <span className="transition-transform group-open:rotate-90">▸</span>
              FRED MCP
            </summary>
            <div className="absolute bottom-full right-0 z-30 mb-2 flex w-56 flex-col items-stretch gap-1 rounded-lg border bg-popover p-2 shadow-lg">
              {MACRO_SERIES.map((item) => (
                <label
                  key={item.id}
                  className="flex cursor-pointer items-center gap-1.5 text-[10px] text-muted-foreground hover:text-foreground"
                >
                  <input
                    type="checkbox"
                    checked={series.has(item.id)}
                    onChange={() => toggleSeries(item.id)}
                    disabled={isSending}
                    className="size-3 accent-foreground"
                  />
                  <span>{item.label}</span>
                  <span className="font-mono text-[9px] text-muted-foreground/70">
                    {item.id}
                  </span>
                </label>
              ))}
              <button
                type="button"
                onClick={askFred}
                disabled={series.size === 0 || isSending}
                className="mt-0.5 rounded-md border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] font-medium transition-colors hover:bg-primary/20 disabled:opacity-40"
              >
                Ask FRED{series.size > 0 ? ` (${series.size})` : ""}
              </button>
            </div>
          </details>
        </div>
        <ProposalQueue />

        <form
          onSubmit={onSubmit}
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
