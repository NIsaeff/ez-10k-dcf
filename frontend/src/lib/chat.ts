export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
};

// TODO(chat-history): every request sends the full conversation, so payload
// size and model input tokens grow with each turn (roughly O(n^2) bytes per
// session). When persistence lands, send only { conversation_id, message }
// and keep history server-side — or at minimum trim to the last N messages /
// a token budget before calling the model.
export async function sendChat(messages: ChatMessage[]): Promise<string> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: messages.map(({ role, content }) => ({ role, content })),
    }),
  });

  if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);

  const data = (await res.json()) as { reply: string };
  return data.reply;
}
