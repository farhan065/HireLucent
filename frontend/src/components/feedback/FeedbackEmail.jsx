import {
  CircleAlert,
  CircleCheck,
  LoaderCircle,
  Mail,
  Send,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { formatDateTime } from '../../lib/jobs.js'
import { highlight, readFeedback, reviewFeedback } from '../../lib/feedback.js'
import Button from '../Button.jsx'
import ConfirmDialog from '../ConfirmDialog.jsx'
import Skeleton from '../Skeleton.jsx'

const LABEL = 'text-xs font-bold uppercase tracking-[0.06em] text-[#6B7890]'
const GROUPS = [
  ['strength', 'Strengths', 'text-success'],
  ['growth', 'Growth areas', 'text-amber'],
  ['level', 'Role level', 'text-navy'],
]

function Badge({ feedback }) {
  if (feedback.status === 'sent') return null
  if (feedback.warnings.length > 0) {
    const count = feedback.warnings.length
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-soft px-3 py-1 text-[13px] font-bold text-amber">
        <TriangleAlert className="size-3.5" aria-hidden="true" />
        {count} fairness {count === 1 ? 'warning' : 'warnings'}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-success-soft px-3 py-1 text-[13px] font-bold text-success">
      <ShieldCheck className="size-3.5" aria-hidden="true" />
      Fairness check passed
    </span>
  )
}

function Body({ text, warnings }) {
  return (
    <div className="rounded-2xl border border-line bg-[#F8FAFE] px-5 py-4.5 text-[15px] leading-relaxed whitespace-pre-wrap text-navy">
      {highlight(text, warnings).map((part, index) =>
        part.mark ? (
          <mark
            key={index}
            className="rounded-sm border-b-2 border-[#E08A00] bg-[#FFE2B8] px-0.5 text-navy"
          >
            {part.text}
          </mark>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </div>
  )
}

// What the email's points are based on. Only the interviewer sees this.
function BasedOn({ evidence }) {
  if (!evidence.length) return null
  return (
    <aside
      aria-label="Where each point comes from"
      className="flex flex-col gap-3.5 rounded-2xl border border-[#EEF2F9] bg-[#FBFCFF] px-5 py-4.5"
    >
      <span className={LABEL}>Based on · only you see this</span>
      {GROUPS.map(([group, title, tone]) => {
        const points = evidence.filter((point) => point.group === group)
        if (!points.length) return null
        return (
          <div key={group} className="flex flex-col gap-1.5">
            <span className={`text-[13px] font-bold ${tone}`}>{title}</span>
            {points.map((point) => (
              <span
                key={`${group}-${point.id}`}
                className="rounded-[10px] border border-line bg-white px-2.5 py-2 text-[13px] leading-snug"
              >
                {group !== 'level' && <strong className="text-navy">{point.id} </strong>}
                {point.text} · {point.note}
              </span>
            ))}
          </div>
        )
      })}
      <span className="text-[12.5px] leading-snug">
        Never in the email: scores, rank, label, other candidates, transcript quotes, the identity
        check or your private note.
      </span>
    </aside>
  )
}

function Preview({ feedback }) {
  return (
    <div className="flex max-h-80 flex-col gap-2 overflow-y-auto rounded-2xl border border-[#EEF2F9] bg-[#F8FAFE] px-4 py-3.5 text-[13.5px] leading-relaxed whitespace-pre-wrap text-navy">
      <span>
        <strong className="font-semibold">Subject:</strong> {feedback.subject}
      </span>
      <span>{feedback.body}</span>
    </div>
  )
}

// One candidate's feedback email: the draft with its fairness result and
// evidence, and the review actions (edit, request changes, discard, approve
// and send, send anyway, try again). Used in the review panel and on the
// assessment page's Decision tab. "onWrite" writes a first draft; "isWriting"
// shows that one is being written.
export default function FeedbackEmail({
  candidateId,
  candidateName,
  version = 0,
  isWriting = false,
  onWrite,
  onChanged,
}) {
  const [feedback, setFeedback] = useState(undefined)
  const [loadError, setLoadError] = useState('')
  const [mode, setMode] = useState('view')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [dialog, setDialog] = useState(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let isCurrent = true
    readFeedback(candidateId)
      .then((loaded) => {
        if (!isCurrent) return
        setFeedback(loaded)
        setLoadError('')
        setMode('view')
      })
      .catch((failure) => isCurrent && setLoadError(failure.message))
    return () => {
      isCurrent = false
    }
  }, [candidateId, version])

  async function send(payload, kind) {
    setBusy(kind)
    setError('')
    try {
      const updated = await reviewFeedback(candidateId, payload)
      setFeedback(updated)
      setDialog(null)
      setMode('view')
      setNote('')
      onChanged?.(updated)
      return updated
    } catch (failure) {
      setError(failure.message)
      return null
    } finally {
      setBusy(null)
    }
  }

  function startEdit() {
    setSubject(feedback.subject)
    setBody(feedback.body)
    setError('')
    setMode('edit')
  }

  async function saveAndSend() {
    const updated = await send({ action: 'edit', subject, body }, 'edit')
    if (updated && !updated.warnings.length) setDialog('send')
  }

  if (loadError) {
    return (
      <p role="alert" className="text-sm font-semibold text-danger">
        {loadError}
      </p>
    )
  }
  if (feedback === undefined) return <Skeleton className="h-72 w-full rounded-2xl" />

  if (isWriting) {
    return (
      <div
        role="status"
        className="flex flex-col gap-3 rounded-2xl border border-line bg-white px-5 py-4.5"
      >
        <span className="flex items-center gap-2.5 text-[15px] font-semibold text-brand-dark">
          <LoaderCircle
            className="size-4.5 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
          Writing the email…
        </span>
        <span className="flex flex-col gap-2" aria-hidden="true">
          {['w-3/4', 'w-full', 'w-5/6', 'w-2/3'].map((width) => (
            <span key={width} className={`h-3 rounded-md bg-[#EEF2F9] ${width}`} />
          ))}
        </span>
        <span className="text-[13px]">Usually 10–30 seconds, including the fairness check.</span>
      </div>
    )
  }

  if (!feedback || feedback.status === 'discarded') {
    return (
      <div className="flex flex-col items-start gap-3 rounded-2xl border border-dashed border-[#A9C8FF] bg-white px-5 py-4.5">
        <span className="font-display text-base font-extrabold text-navy">
          {feedback ? 'Draft discarded' : 'No email written yet'}
        </span>
        <span className="text-sm">
          {feedback
            ? 'Nothing was sent. Write it again when you are ready.'
            : `The email to ${candidateName} is written from their own results and checked for fairness before you see it.`}
        </span>
        {onWrite && (
          <Button className="min-h-10.5 text-sm" onClick={onWrite}>
            <Sparkles className="size-4" aria-hidden="true" />
            {feedback ? 'Write again' : 'Write email'}
          </Button>
        )}
      </div>
    )
  }

  const isSent = feedback.status === 'sent' || feedback.status === 'sending'
  const isOpen = ['waiting_review', 'failed'].includes(feedback.status)
  const hasWarnings = feedback.warnings.length > 0
  const isAi = feedback.written_by === 'ai'

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge feedback={feedback} />
        <span className="rounded-full bg-mist px-3 py-1 text-[13px] font-semibold text-[#44526B]">
          {isAi ? `Written by the AI · ${formatDateTime(feedback.updated_at)}` : 'Fixed message'}
        </span>
      </div>

      {feedback.status === 'sent' && (
        <p className="flex items-start gap-2.5 rounded-2xl bg-success-soft px-4 py-3 text-sm leading-snug text-[#0B5C41]">
          <CircleCheck className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
          <span>
            <strong>Sent</strong> on {formatDateTime(feedback.sent_at)}
            {feedback.approved_by_name ? ` · approved by ${feedback.approved_by_name}` : ''}
            {feedback.sent_anyway ? ' · sent with its fairness warnings' : ''}
          </span>
        </p>
      )}

      {feedback.status === 'failed' && (
        <p
          role="alert"
          className="flex items-start gap-2.5 rounded-2xl border border-[#F3C4C0] bg-white px-4 py-3 text-sm leading-snug text-danger"
        >
          <CircleAlert className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
          <span>
            <strong>Not sent.</strong> {feedback.error_message} The draft is kept.
          </span>
        </p>
      )}

      {hasWarnings && isOpen && mode === 'view' && (
        <div
          role="alert"
          className="flex gap-3 rounded-2xl border border-[#F3D9A8] bg-[#FFFBF3] px-4 py-3.5 text-sm leading-relaxed text-[#6B3A00]"
        >
          <TriangleAlert className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
          <ul className="flex flex-col gap-1">
            {feedback.warnings.map((warning) => (
              <li key={warning.code}>
                <strong>{warning.message.split(': ')[0]}</strong>
                {warning.message.includes(': ') &&
                  `: ${warning.message.split(': ').slice(1).join(': ')}`}
              </li>
            ))}
            <li>Edit it, ask for changes, or send it anyway after checking.</li>
          </ul>
        </div>
      )}

      {mode === 'edit' ? (
        <div className="flex flex-col gap-3.5">
          <label className="flex flex-col gap-1.5 text-[13.5px] font-semibold text-navy">
            Subject
            <input
              id={`feedback-subject-${candidateId}`}
              value={subject}
              maxLength={255}
              onChange={(event) => setSubject(event.target.value)}
              className="min-h-11 rounded-xl border-[1.5px] border-line px-3.5 text-[15px] font-normal text-navy focus:border-brand focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-[13.5px] font-semibold text-navy">
            Message
            <textarea
              id={`feedback-body-${candidateId}`}
              value={body}
              rows={16}
              maxLength={3000}
              onChange={(event) => setBody(event.target.value)}
              className="resize-y rounded-2xl border-[1.5px] border-brand px-4 py-3.5 text-[15px] leading-relaxed font-normal text-navy focus:outline-none"
            />
          </label>
          <span className="text-[13px]">
            Your text is checked again when you save, with the same rules as the AI's draft.
          </span>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-1 text-sm">
            <span>
              <strong className="font-semibold text-navy">To:</strong> {candidateName}
            </span>
            <span>
              <strong className="font-semibold text-navy">Subject:</strong> {feedback.subject}
            </span>
          </div>
          <Body text={feedback.body} warnings={isOpen ? feedback.warnings : []} />
        </>
      )}

      <BasedOn evidence={feedback.evidence} />

      {error && (
        <p role="alert" className="text-sm font-semibold text-danger">
          {error}
        </p>
      )}

      {isOpen && mode === 'view' && (
        <div className="flex flex-wrap items-center justify-between gap-2.5 border-t border-[#EEF2F9] pt-4">
          <button
            type="button"
            onClick={() => setDialog('discard')}
            className="min-h-11 px-1.5 text-[14.5px] font-semibold text-danger hover:opacity-80"
          >
            Discard
          </button>
          <div className="flex flex-wrap items-center gap-2">
            {isAi && (
              <button
                type="button"
                onClick={() => {
                  setError('')
                  setDialog('changes')
                }}
                className="min-h-11 px-3 text-[14.5px] font-semibold text-brand hover:text-brand-dark"
              >
                Request changes
              </button>
            )}
            {hasWarnings && (
              <button
                type="button"
                onClick={() => setDialog('anyway')}
                className="min-h-11 px-3 text-[14.5px] font-semibold text-amber hover:opacity-80"
              >
                Send anyway
              </button>
            )}
            <Button
              variant={hasWarnings ? 'primary' : 'outline'}
              className="min-h-11"
              onClick={startEdit}
            >
              Edit
            </Button>
            {!hasWarnings && (
              <Button className="min-h-11" onClick={() => setDialog('send')}>
                <Send className="size-4" aria-hidden="true" />
                {feedback.status === 'failed' ? 'Try again' : 'Approve and send'}
              </Button>
            )}
          </div>
        </div>
      )}

      {mode === 'edit' && (
        <div className="flex flex-wrap justify-end gap-2.5 border-t border-[#EEF2F9] pt-4">
          <Button
            variant="soft"
            className="min-h-11"
            disabled={busy !== null}
            onClick={() => setMode('view')}
          >
            Cancel
          </Button>
          <Button
            variant="outline"
            className="min-h-11"
            disabled={busy !== null || !body.trim() || !subject.trim()}
            onClick={() => send({ action: 'edit', subject, body }, 'edit')}
          >
            {busy === 'edit' ? 'Checking…' : 'Save and check'}
          </Button>
          <Button
            className="min-h-11"
            disabled={busy !== null || !body.trim() || !subject.trim()}
            onClick={saveAndSend}
          >
            <Send className="size-4" aria-hidden="true" />
            Approve and send
          </Button>
        </div>
      )}

      {isSent && feedback.status === 'sending' && (
        <p role="status" className="flex items-center gap-2 text-sm font-semibold text-brand-dark">
          <LoaderCircle
            className="size-4 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
          Sending to {candidateName}…
        </p>
      )}

      {(dialog === 'send' || dialog === 'anyway') && (
        <ConfirmDialog
          title={`Send this email to ${candidateName}?`}
          icon={Mail}
          isWide
          confirmLabel="Send email"
          busyLabel="Sending…"
          confirmVariant="primary"
          isBusy={busy === 'send'}
          error={error}
          onConfirm={() =>
            send({ action: dialog === 'anyway' ? 'send_anyway' : 'approve' }, 'send')
          }
          onCancel={() => setDialog(null)}
        >
          <p>
            It is sent from the Google account signed in to HireLucent. After sending, the decision
            is locked.
          </p>
          {dialog === 'anyway' && (
            <p className="rounded-xl bg-amber-soft px-3.5 py-2.5 text-sm text-amber">
              This email still has {feedback.warnings.length} fairness{' '}
              {feedback.warnings.length === 1 ? 'warning' : 'warnings'}:{' '}
              {feedback.warnings.map((warning) => warning.message.split(':')[0]).join('; ')}.
            </p>
          )}
          <Preview feedback={feedback} />
        </ConfirmDialog>
      )}

      {dialog === 'changes' && (
        <ConfirmDialog
          title="What should change?"
          confirmLabel="Rewrite"
          busyLabel="Rewriting…"
          confirmVariant="primary"
          isBusy={busy === 'changes'}
          confirmDisabled={!note.trim()}
          error={error}
          onConfirm={() => send({ action: 'request_changes', note }, 'changes')}
          onCancel={() => setDialog(null)}
        >
          <label className="flex flex-col gap-1.5 text-[13.5px] font-semibold text-navy">
            Your note to the AI
            <textarea
              id={`feedback-note-${candidateId}`}
              value={note}
              rows={3}
              maxLength={1000}
              onChange={(event) => setNote(event.target.value)}
              placeholder="For example: keep it shorter and mention the good answer on SQL tuning."
              className="resize-none rounded-xl border-[1.5px] border-brand px-3 py-2.5 text-sm leading-relaxed font-normal text-navy focus:outline-none"
            />
          </label>
          <span className="text-[12.5px]">
            The note is never put in the email as it is; the rules still apply. The old draft stays
            until the new one is ready.
          </span>
        </ConfirmDialog>
      )}

      {dialog === 'discard' && (
        <ConfirmDialog
          title="Discard this draft?"
          confirmLabel="Discard"
          busyLabel="Discarding…"
          isBusy={busy === 'discard'}
          error={error}
          onConfirm={() => send({ action: 'discard' }, 'discard')}
          onCancel={() => setDialog(null)}
        >
          <p>Nothing is sent. You can write the email again later.</p>
        </ConfirmDialog>
      )}
    </div>
  )
}
