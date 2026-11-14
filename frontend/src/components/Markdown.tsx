import { Streamdown } from "streamdown"

import "streamdown/styles.css"

/**
 * Model replies are markdown. Streamdown is the renderer the AI Elements
 * Message pattern uses: GFM tables/lists, sanitized HTML, and shiki-highlighted
 * code blocks that match the rest of the app.
 */
export function Markdown({ text }: { text: string }) {
  return (
    <Streamdown className="max-w-none text-sm leading-relaxed" mode="static">
      {text}
    </Streamdown>
  )
}
