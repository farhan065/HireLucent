import { CARD_STATUS, rangeLabel } from '../../lib/interviews.js'
import Button from '../Button.jsx'
import StatusChip from '../StatusChip.jsx'
import { OutcomeLine, WhenYouApprove } from './InterviewCardParts.jsx'

const KEEP_FEEDBACK = 'Keep the interview. Do not cancel it.'

function Detail({ label, children }) {
  return (
    <div className="flex gap-3 text-sm">
      <span className="w-24 shrink-0">{label}</span>
      <span className="min-w-0 font-semibold text-navy">{children}</span>
    </div>
  )
}

// The agent's request to move or cancel one interview. "kind" is
// "reschedule" or "cancel_interview". Nothing is sent until the interviewer
// approves.
export default function InterviewChangeCard({
  item,
  canAct,
  onApprove,
  onReject,
  onRequestChanges,
}) {
  const args = item.arguments ?? {}
  const isMove = item.kind === 'reschedule'
  const isWaiting = item.status === 'waiting'
  const chip = CARD_STATUS[item.status] ?? CARD_STATUS.changed
  const zone = args.time_zone
  const name = args.candidate_name ?? `Candidate ${args.candidate_id}`
  const when = rangeLabel(args.start, args.end, zone) || args.when
  const zoneNote = args.time_zone_label ? ` (${args.time_zone_label})` : ''
  const result = item.result

  const title = isMove
    ? isWaiting
      ? 'Your decision: move an interview'
      : 'Move an interview'
    : isWaiting
      ? 'Your decision: cancel an interview'
      : 'Cancel an interview'

  return (
    <article
      className={`overflow-hidden rounded-2xl border bg-white ${
        isWaiting ? 'border-brand shadow-card' : 'border-line'
      } ${item.status === 'changed' ? 'opacity-70' : ''}`}
    >
      <header className="flex flex-wrap items-center justify-between gap-2.5 bg-mist px-4 py-3">
        <span className="font-display text-[15px] font-bold text-navy">{title}</span>
        <StatusChip tone={chip.tone}>{chip.label}</StatusChip>
      </header>

      <div className="flex flex-col gap-2 px-4 py-3.5">
        <Detail label="Candidate">{name}</Detail>
        {isMove ? (
          <>
            <Detail label="Now">
              {rangeLabel(args.previous_start, args.previous_end, zone) || args.previous_when}
            </Detail>
            <Detail label="New time">
              {when}
              {zoneNote}
            </Detail>
          </>
        ) : (
          <Detail label="When">
            {when}
            {zoneNote}
          </Detail>
        )}
      </div>

      {isWaiting && (
        <WhenYouApprove
          preview={args.email_preview}
          lines={
            isMove
              ? [
                  {
                    icon: 'mail',
                    text: `${name} gets an updated invitation with the new time and a new private link.`,
                  },
                  { icon: 'calendar', text: 'The interview moves in their calendar.' },
                  { icon: 'lock', text: 'The old link stops working.' },
                ]
              : [
                  { icon: 'mail', text: `${name} gets Google Calendar's cancellation notice.` },
                  { icon: 'calendar', text: 'The interview is removed from their calendar.' },
                  {
                    icon: 'lock',
                    text: 'Their link stops working, and they go back on the shortlist.',
                  },
                ]
          }
        />
      )}

      {result && (
        <div className="border-t border-line px-4 py-1.5">
          <OutcomeLine kind={result.warning ? 'warning' : 'done'} name={result.candidate_name}>
            {result.warning ? (
              <span className="text-warning">{result.warning}</span>
            ) : isMove ? (
              'New time and link sent'
            ) : (
              'Cancelled, and the candidate was told'
            )}
          </OutcomeLine>
        </div>
      )}

      {isWaiting && canAct && (
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3.5">
          <span className="text-sm">or type what to change below</span>
          <div className="flex flex-wrap gap-2.5">
            {isMove ? (
              <>
                <Button variant="outline" onClick={onRequestChanges}>
                  Request changes
                </Button>
                <Button onClick={onApprove}>Approve and send the new time</Button>
              </>
            ) : (
              <>
                <Button variant="outline" onClick={() => onReject(KEEP_FEEDBACK)}>
                  Keep the interview
                </Button>
                <Button variant="danger" onClick={onApprove}>
                  Approve and cancel
                </Button>
              </>
            )}
          </div>
        </footer>
      )}
    </article>
  )
}
