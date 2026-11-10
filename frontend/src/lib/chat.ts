export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
};

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
