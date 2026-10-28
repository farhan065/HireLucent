import { useCallback, useState } from 'react'

// How many of the other person's messages arrived while the messages were
// hidden. Call markSeen when hiding them, so only later ones count.
export function useUnread(messages, isVisible) {
  const received = messages.filter((message) => !message.isMine).length
  const [seen, setSeen] = useState(0)
  const markSeen = useCallback(() => setSeen(received), [received])
  return [isVisible ? 0 : Math.max(0, received - seen), markSeen]
}
