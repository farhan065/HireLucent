import { Send, Sparkles, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import Button from '../Button.jsx'
import ConfirmDialog from '../ConfirmDialog.jsx'

// The counts of a list's emails as small chips.
export function EmailCounts({ counts }) {
  const chips = [
    [counts.none, 'not written', 'bg-[#EEF1F6] text-[#44526B]'],
    [counts.ready, 'ready to send', 'bg-success-soft text-success'],
    [counts.review, 'needs your review', 'bg-amber-soft text-amber'],
    [counts.sent, 'sent', 'bg-tint text-brand-dark'],
  ].filter(([count]) => count > 0)
  if (!chips.length) return null
  return (
    <span className="flex flex-wrap gap-2 text-[13px] font-semibold">
      {chips.map(([count, label, className]) => (
        <span key={label} className={`rounded-full px-3 py-1.5 ${className}`}>
          {count} {label}
        </span>
      ))}
    </span>
  )
}

// Write emails (every one not written yet) and Send all passed (after a
// confirm that names who is sent and who still needs review).
export default function EmailButtons({
  toWrite,
  ready,
  needReview,
  isRunning,
  onWrite,
  onSendAll,
}) {
  const [isConfirming, setIsConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const busyTitle = isRunning
    ? 'Emails are being written or sent. Wait for it to finish.'
    : undefined

  async function sendAll() {
    setBusy(true)
    const started = await onSendAll()
    setBusy(false)
    if (started) setIsConfirming(false)
  }

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <Button
        variant="outline"
        className="min-h-11 text-[14.5px]"
        disabled={isRunning || toWrite.length === 0}
        title={busyTitle}
        onClick={() => onWrite(toWrite.map((person) => person.id))}
      >
        <Sparkles className="size-4.5" aria-hidden="true" />
        Write emails
        <span className="rounded-full bg-tint px-2 py-0.5 text-xs">{toWrite.length}</span>
      </Button>
      <Button
        className="min-h-11 text-[14.5px]"
        disabled={isRunning || ready.length === 0}
        title={busyTitle}
        onClick={() => setIsConfirming(true)}
      >
        <Send className="size-4.5" aria-hidden="true" />
        Send all passed
        <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs">{ready.length}</span>
      </Button>

      {isConfirming && (
        <ConfirmDialog
          title={`Send ${ready.length} ${ready.length === 1 ? 'email' : 'emails'}?`}
          confirmLabel={`Send ${ready.length} ${ready.length === 1 ? 'email' : 'emails'}`}
          busyLabel="Starting…"
          confirmVariant="primary"
          isWide
          isBusy={busy}
          onConfirm={sendAll}
          onCancel={() => setIsConfirming(false)}
        >
          <p>
            These drafts passed the fairness check. They are sent one after another; you can leave
            the page.
          </p>
          <p className="rounded-2xl border border-[#EEF2F9] bg-[#F8FAFE] px-4 py-3 text-sm text-navy">
            {ready.map((person) => person.name).join(' · ')}
          </p>
          {needReview.length > 0 && (
            <p className="flex gap-2.5 rounded-2xl border border-[#F3D9A8] bg-[#FFFBF3] px-4 py-3 text-sm text-[#6B3A00]">
              <TriangleAlert className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
              <span>
                <strong>
                  {needReview.length} {needReview.length === 1 ? 'email needs' : 'emails need'} your
                  review first
                </strong>{' '}
                and won't be sent: {needReview.map((person) => person.name).join(', ')}. Open them
                from the list.
              </span>
            </p>
          )}
        </ConfirmDialog>
      )}
    </div>
  )
}
