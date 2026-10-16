import { ArrowDown, CircleAlert, Mic, ScrollText, UserRound } from 'lucide-react'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { clock } from '../../lib/interviews.js'
import { fromStart } from '../../lib/room.js'
import Skeleton from '../Skeleton.jsx'
import StatusChip from '../StatusChip.jsx'

const CHIPS = {
  waiting: { tone: 'neutral', label: 'Not started' },
  loading: { tone: 'neutral', label: 'Loading' },
  listening: { tone: 'success', label: 'Listening' },
  paused: { tone: 'warning', label: 'Paused' },
  off: { tone: 'danger', label: 'Not available' },
}

// Closer than this to the bottom counts as reading the latest lines.
const AT_BOTTOM_PX = 48

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}

// One row per saved turn, in the order spoken, then a row for each person
// still speaking, with their words so far.
function transcriptRows(turns, live) {
  const rows = turns.map((turn) => ({
    key: turn.id,
    speaker: turn.speaker,
    startMs: turn.start_ms,
    text: turn.text,
    isLive: false,
  }))
  Object.entries(live)
    .filter(([, words]) => words?.text)
    .sort(([, a], [, b]) => a.start_ms - b.start_ms)
    .forEach(([speaker, words]) =>
      rows.push({
        key: `live-${speaker}`,
        speaker,
        startMs: words.start_ms,
        text: words.text,
        isLive: true,
      }),
    )
  return rows
}

function Avatar({ isInterviewer, candidateName }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-flex size-8 items-center justify-center rounded-full text-[11px] font-bold ${
        isInterviewer ? 'bg-tint text-brand' : 'bg-teal-soft text-teal'
      }`}
    >
      {isInterviewer ? 'You' : initials(candidateName)}
    </span>
  )
}

function Speaking() {
  return (
    <span className="inline-flex items-center gap-1.5 font-semibold text-teal">
      <span className="inline-flex gap-0.5" aria-hidden="true">
        <span className="size-1.5 animate-pulse rounded-full bg-current" />
        <span className="size-1.5 animate-pulse rounded-full bg-current opacity-60 [animation-delay:150ms]" />
        <span className="size-1.5 animate-pulse rounded-full bg-current opacity-30 [animation-delay:300ms]" />
      </span>
      speaking
    </span>
  )
}

function Centered({ icon: Icon, tone, title, children }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 px-8 py-6 text-center text-sm">
      <span className={`inline-flex size-11 items-center justify-center rounded-full ${tone}`}>
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <p className="mt-1 font-display text-[15px] font-bold text-navy">{title}</p>
      <p className="max-w-md leading-relaxed">{children}</p>
    </div>
  )
}

function Banner({ tone, title, children }) {
  const colors =
    tone === 'warning'
      ? 'border-[#F6DFB0] bg-warning-soft text-warning'
      : 'border-danger/20 bg-danger-soft text-danger'
  return (
    <div
      role="alert"
      className={`mx-4 mt-3 flex gap-2.5 rounded-2xl border px-3 py-2.5 text-[13px] ${colors}`}
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p className="leading-snug">
        <strong className="font-bold">{title}</strong> {children}
      </p>
    </div>
  )
}

// The interviewer's live transcript under the video. Newest lines at the
// bottom; it follows them unless the interviewer scrolls up to read, and
// then offers to jump back. Only the interviewer sees this panel.
export default function LiveTranscript({ transcript, candidateName, startedAt, className = '' }) {
  const { turns, live, state } = transcript
  const firstName = candidateName.split(/\s+/)[0]
  const rows = useMemo(() => transcriptRows(turns, live), [turns, live])
  const scrollRef = useRef(null)
  // How many turns there were when the interviewer scrolled up; null while
  // they follow the latest lines.
  const [readUpTo, setReadUpTo] = useState(null)
  const chip = CHIPS[state]

  useLayoutEffect(() => {
    const element = scrollRef.current
    if (element && readUpTo === null) element.scrollTop = element.scrollHeight
  }, [rows, readUpTo])

  function handleScroll() {
    const element = scrollRef.current
    const isAtBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight < AT_BOTTOM_PX
    setReadUpTo((current) => (isAtBottom ? null : (current ?? turns.length)))
  }

  function jumpToLatest() {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    setReadUpTo(null)
  }

  const spokenAt = (ms) =>
    startedAt ? `Said at ${clock(new Date(new Date(startedAt).getTime() + ms))}` : undefined
  const newLines = readUpTo === null ? 0 : turns.length - readUpTo

  let body
  if (state === 'waiting') {
    body = (
      <Centered
        icon={UserRound}
        tone="bg-mist text-body"
        title={`The transcript starts when you let ${firstName} in`}
      >
        From then on, what each of you says is written down here.
      </Centered>
    )
  } else if (state === 'loading') {
    body = (
      <div className="flex flex-col gap-4 px-4 py-4" aria-label="Loading what was said so far">
        {['w-5/6', 'w-2/3', 'w-3/4'].map((width) => (
          <div key={width} className="grid grid-cols-[32px_minmax(0,1fr)] gap-3">
            <span aria-hidden="true" className="size-8 animate-shimmer rounded-full" />
            <div className="flex flex-col gap-2 pt-1">
              <Skeleton className="h-3 w-24" />
              <Skeleton className={`h-3 ${width}`} />
            </div>
          </div>
        ))}
      </div>
    )
  } else if (state === 'off' && rows.length === 0) {
    body = (
      <Centered
        icon={CircleAlert}
        tone="bg-danger-soft text-danger"
        title="The live transcript is not available"
      >
        The interview goes on normally. The transcript continues by itself once the transcription
        service is back.
      </Centered>
    )
  } else {
    body = (
      <div className="flex min-h-0 flex-1 flex-col">
        {state === 'paused' && (
          <Banner tone="warning" title="Transcription paused, reconnecting…">
            The interview goes on, and everything said so far is saved.
          </Banner>
        )}
        {state === 'off' && (
          <Banner tone="danger" title="The live transcript is not available.">
            The interview goes on, and everything said so far is saved.
          </Banner>
        )}
        {rows.length === 0 ? (
          <Centered icon={Mic} tone="bg-success-soft text-success" title="Listening">
            Nothing has been said yet. Words appear here as each of you speaks.
          </Centered>
        ) : (
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto py-3 pr-6 pl-4"
          >
            {rows.map((row) => {
              const isInterviewer = row.speaker === 'interviewer'
              return (
                <div key={row.key} className="grid grid-cols-[32px_minmax(0,1fr)] gap-3">
                  <Avatar isInterviewer={isInterviewer} candidateName={candidateName} />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-x-1.5 text-[12.5px]">
                      <strong className="font-bold text-navy">
                        {isInterviewer ? 'You' : firstName}
                      </strong>
                      <span className="tabular-nums" title={spokenAt(row.startMs)}>
                        {fromStart(row.startMs)}
                      </span>
                      {row.isLive && <Speaking />}
                    </div>
                    <p
                      className={`mt-0.5 text-[14px] leading-normal ${row.isLive ? 'text-[#8A97AE]' : 'text-navy'}`}
                    >
                      {row.text}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  return (
    <section
      aria-label="Live transcript"
      className={`flex min-h-0 flex-col overflow-hidden rounded-card border border-line bg-white shadow-card ${className}`}
    >
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line px-4 py-2.5">
        <span className="flex items-center gap-2.5">
          <span className="flex items-center gap-2 font-display text-[15px] font-bold text-navy">
            <ScrollText className="size-4.5 text-brand" aria-hidden="true" />
            Live transcript
          </span>
          <StatusChip tone={chip.tone}>{chip.label}</StatusChip>
        </span>
        <span className="text-xs">Only you see this</span>
      </header>
      <div className="relative flex min-h-0 flex-1 flex-col">
        {body}
        {newLines > 0 && (
          <button
            type="button"
            onClick={jumpToLatest}
            className="absolute bottom-3.5 left-1/2 inline-flex min-h-9.5 -translate-x-1/2 items-center gap-1.5 rounded-full bg-brand px-4 font-display text-[13px] font-bold text-white shadow-button hover:bg-brand-dark"
          >
            <ArrowDown className="size-4" aria-hidden="true" />
            {newLines} new · Jump to latest
          </button>
        )}
      </div>
    </section>
  )
}
