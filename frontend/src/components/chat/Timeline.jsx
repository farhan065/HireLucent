import { useEffect, useRef } from 'react'
import { splitDraft } from '../../lib/drafts.js'
import DescriptionCard from './DescriptionCard.jsx'
import {
  AssistantRow,
  AssistantText,
  NoteLine,
  ThinkingDots,
  UserBubble,
} from './MessageBubble.jsx'
import RequirementsCard from './RequirementsCard.jsx'

function TimelineItem({ item, canAct, onApprove, onConfirm }) {
  if (item.kind === 'user') return <UserBubble text={item.text} />
  if (item.kind === 'note') return <NoteLine text={item.text} />
  if (item.kind === 'assistant') {
    return (
      <AssistantRow>
        <AssistantText text={item.text} />
      </AssistantRow>
    )
  }
  if (item.kind === 'description') {
    return (
      <AssistantRow>
        <DescriptionCard item={item} canAct={canAct} onApprove={onApprove} />
      </AssistantRow>
    )
  }
  return (
    <AssistantRow>
      <RequirementsCard item={item} canAct={canAct} onConfirm={onConfirm} />
    </AssistantRow>
  )
}

// The reply that is being written right now. If it has a title line it is
// already shown as a description card, otherwise as plain text.
function StreamingReply({ text }) {
  if (!text) {
    return (
      <AssistantRow>
        <ThinkingDots />
      </AssistantRow>
    )
  }
  const draft = splitDraft(text)
  return (
    <AssistantRow>
      {draft ? (
        <>
          {draft.intro && <AssistantText text={draft.intro} />}
          <DescriptionCard
            item={{ status: 'writing', title: draft.title, text: draft.body }}
            canAct={false}
          />
        </>
      ) : (
        <AssistantText text={text} isWriting />
      )}
    </AssistantRow>
  )
}

// The conversation: every bubble, note and card in the order it happened.
export default function Timeline({
  items,
  pendingText,
  streamingText,
  isBusy,
  onApprove,
  onConfirm,
}) {
  const endRef = useRef(null)

  // Keep the newest content in view as it arrives.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [items.length, streamingText, isBusy])

  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      {items.map((item) => (
        <TimelineItem
          key={item.id}
          item={item}
          canAct={!isBusy}
          onApprove={onApprove}
          onConfirm={onConfirm}
        />
      ))}
      {pendingText && <UserBubble text={pendingText} />}
      {isBusy && <StreamingReply text={streamingText} />}
      <div ref={endRef} />
    </div>
  )
}
