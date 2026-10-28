import { Fragment } from 'react'
import { clock } from '../../lib/interviews.js'
import { fromStart } from '../../lib/room.js'
import { splitText } from '../../lib/transcript.js'
import { Avatar } from '../room/LiveTranscript.jsx'

// A line between the turns at every 5 minutes, to keep one's place.
const DIVIDER_MS = 5 * 60 * 1000

function Divider({ ms }) {
  return (
    <div className="my-2 flex items-center gap-3 text-xs font-semibold text-[#6B7890] tabular-nums">
      <span aria-hidden="true" className="h-px flex-1 bg-[#EEF2F9]" />
      {fromStart(ms)}
      <span aria-hidden="true" className="h-px flex-1 bg-[#EEF2F9]" />
    </div>
  )
}

function Text({ text, query, currentAt }) {
  return splitText(text, query).map((piece) => {
    if (!piece.isMatch) return <Fragment key={piece.at}>{piece.text}</Fragment>
    const isCurrent = piece.at === currentAt
    return (
      <mark
        key={piece.at}
        className={`rounded px-0.5 text-navy ${
          isCurrent ? 'bg-[#F7B547] ring-2 ring-[#B45309]' : 'bg-[#FFE2A8]'
        }`}
      >
        {piece.text}
      </mark>
    )
  })
}

// Every turn of the finished interview, one row each as in the live
// transcript, with the search matches marked. "data-turn", "data-ms" and
// "data-end" let the page scroll to a turn and see which part is on screen.
// focusTurnId marks the turn the page was opened at, for example from an
// answer's time on the assessment page.
export default function TranscriptTurns({
  turns,
  candidateName,
  query,
  currentMatch,
  focusTurnId = null,
}) {
  const firstName = candidateName.split(/\s+/)[0]
  return (
    <div className="flex max-w-[920px] flex-col gap-1.5 py-4.5 pr-7 pl-5">
      {turns.map((turn, index) => {
        const isInterviewer = turn.speaker === 'interviewer'
        const boundary = Math.floor(turn.start_ms / DIVIDER_MS)
        const previous = index > 0 ? Math.floor(turns[index - 1].start_ms / DIVIDER_MS) : 0
        const hasCurrent = currentMatch?.turnId === turn.id
        const isFocus = focusTurnId === turn.id
        return (
          <Fragment key={turn.id}>
            {boundary > previous && <Divider ms={boundary * DIVIDER_MS} />}
            <div
              data-turn={turn.id}
              data-ms={turn.start_ms}
              data-end={turn.end_ms}
              className={`grid grid-cols-[32px_minmax(0,1fr)] gap-3 rounded-2xl px-2.5 py-2 ${
                hasCurrent ? 'bg-warning-soft/60' : isFocus ? 'bg-tint ring-1 ring-[#A9C8FF]' : ''
              }`}
            >
              <Avatar isInterviewer={isInterviewer} candidateName={candidateName} />
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-x-1.5 text-[12.5px]">
                  <strong className="font-bold text-navy">
                    {isInterviewer ? 'You' : firstName}
                  </strong>
                  <span
                    className="tabular-nums"
                    title={turn.spoken_at ? `Said at ${clock(turn.spoken_at)}` : undefined}
                  >
                    {fromStart(turn.start_ms)}
                  </span>
                </div>
                <p className="mt-0.5 text-[14.5px] leading-relaxed text-navy">
                  <Text
                    text={turn.text}
                    query={query}
                    currentAt={hasCurrent ? currentMatch.at : null}
                  />
                </p>
              </div>
            </div>
          </Fragment>
        )
      })}
    </div>
  )
}
