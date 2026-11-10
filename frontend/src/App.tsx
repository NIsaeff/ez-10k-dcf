import { useState, type FormEvent } from "react"

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
import { ModeToggle } from "@/components/mode-toggle"
import { sendChat, type ChatMessage } from "@/lib/chat"

const initialMessages: ChatMessage[] = [
  {
    id: "assistant-1",
    role: "assistant",
    content: "Ask me about a company's 10-K and I'll pull the financials and build a DCF.",
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
  const reply = await sendChat(next)
  setMessages((current) => [
    ...current,
    { id: crypto.randomUUID(), role: "assistant", content: reply },
  ])
} catch (error) {
  const message = error instanceof Error ? error.message : String(error)
  setMessages((current) => [
    ...current,
    { id: crypto.randomUUID(), role: "assistant", content: `Request failed: ${message}` },
  ])
} finally {
  setIsSending(false)
}
}

  return (
    <main className="flex h-svh flex-col bg-background text-foreground">
      <header className="flex items-center justify-between border-b px-6 py-4">
        <h1 className="text-lg font-semibold">EZ-10k: Agentic DCF</h1>
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
        <form onSubmit={send} className="mx-auto flex w-full max-w-3xl gap-2">
          <Input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask about a 10-K..."
            aria-label="Message"
            disabled={isSending}
          />
          <Button type="submit" disabled={isSending || !draft.trim()}>
            Send
          </Button>
        </form>
      </footer>
    </main>
  )
}

