import { useEffect, useRef } from 'react'
import { splitDraft } from '../../lib/drafts.js'
import DescriptionCard from './DescriptionCard.jsx'
import InterviewChangeCard from './InterviewChangeCard.jsx'
import {
  AssistantRow,
  AssistantText,
  NoteLine,
  ThinkingDots,
  UserBubble,
} from './MessageBubble.jsx'
import PostCard from './PostCard.jsx'
import PublishedCard from './PublishedCard.jsx'
import RequirementsCard from './RequirementsCard.jsx'
import ScheduleCard from './ScheduleCard.jsx'

function TimelineItem({
  item,
  canAct,
  canEdit,
  jobId,
  onApprove,
  onConfirm,
  onEdit,
  onPublish,
  onEditPost,
  onApproveAction,
  onEditAction,
  onRejectAction,
  onRequestChanges,
}) {
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
        <DescriptionCard
          item={item}
          canAct={canAct}
          canEdit={canEdit}
          onApprove={onApprove}
          onEdit={onEdit}
        />
      </AssistantRow>
    )
  }
  if (item.kind === 'post') {
    return (
      <AssistantRow>
        <PostCard item={item} canAct={canAct} onPublish={onPublish} onEdit={onEditPost} />
      </AssistantRow>
    )
  }
  if (item.kind === 'published') {
    return (
      <AssistantRow>
        <PublishedCard url={item.text} />
      </AssistantRow>
    )
  }
  if (item.kind === 'requirements') {
    return (
      <AssistantRow>
        <RequirementsCard item={item} canAct={canAct} onConfirm={onConfirm} />
      </AssistantRow>
    )
  }
  if (item.kind === 'schedule') {
    return (
      <AssistantRow>
        <ScheduleCard
          item={item}
          canAct={canAct}
          jobId={jobId}
          onApprove={onApproveAction}
          onCheck={onEditAction}
          onRequestChanges={onRequestChanges}
        />
      </AssistantRow>
    )
  }
  if (item.kind === 'reschedule' || item.kind === 'cancel_interview') {
    return (
      <AssistantRow>
        <InterviewChangeCard
          item={item}
          canAct={canAct}
          onApprove={onApproveAction}
          onReject={onRejectAction}
          onRequestChanges={onRequestChanges}
        />
      </AssistantRow>
    )
  }
  return null
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
  canEdit,
  jobId,
  onApprove,
  onConfirm,
  onEdit,
  onPublish,
  onEditPost,
  onApproveAction,
  onEditAction,
  onRejectAction,
  onRequestChanges,
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
          canEdit={canEdit}
          jobId={jobId}
          onApprove={onApprove}
          onConfirm={onConfirm}
          onEdit={onEdit}
          onPublish={onPublish}
          onEditPost={onEditPost}
          onApproveAction={onApproveAction}
          onEditAction={onEditAction}
          onRejectAction={onRejectAction}
          onRequestChanges={onRequestChanges}
        />
      ))}
      {pendingText && <UserBubble text={pendingText} />}
      {isBusy && <StreamingReply text={streamingText} />}
      <div ref={endRef} />
    </div>
  )
}
