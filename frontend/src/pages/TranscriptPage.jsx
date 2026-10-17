import { ArrowLeft, ChevronDown, ChevronUp, CircleAlert, Download, Search, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import Button from '../components/Button.jsx'
import Skeleton from '../components/Skeleton.jsx'
import StatusChip from '../components/StatusChip.jsx'
import TranscriptTimeline from '../components/transcript/TranscriptTimeline.jsx'
import TranscriptTurns from '../components/transcript/TranscriptTurns.jsx'
import { readInterview, readTranscript } from '../lib/room.js'
import {
  downloadText,
  fileName,
  fileText,
  findMatches,
  lengthMs,
  tookLabel,
  whenLabel,
} from '../lib/transcript.js'

const STATUSES = {
  completed: { tone: 'success', label: 'Completed' },
  in_progress: { tone: 'info', label: 'In progress' },
  scheduled: { tone: 'amber', label: 'Scheduled' },
  cancelled: { tone: 'neutral', label: 'Cancelled' },
}

const ICON_BUTTON =
  'inline-flex size-10 items-center justify-center rounded-[10px] border border-line bg-white text-navy hover:bg-tint disabled:cursor-not-allowed disabled:border-[#EEF2F9] disabled:bg-[#F7F9FC] disabled:text-[#A8B3C6]'

function LoadingTranscript() {
  return (
    <div role="status" aria-label="Loading the transcript" className="flex flex-col gap-5">
      <Skeleton className="h-4 w-72" />
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-96" />
        <Skeleton className="h-5 w-[28rem]" />
      </div>
      <div className="flex flex-col overflow-hidden rounded-card border border-line bg-white shadow-card">
        <div className="flex gap-2.5 border-b border-line px-5 py-3.5">
          <Skeleton className="h-11 w-64 rounded-xl" />
          <Skeleton className="h-10 w-22" />
        </div>
        <div className="border-b border-line px-5 py-4">
          <Skeleton className="h-7.5 w-full" />
        </div>
        <div className="flex flex-col gap-4.5 px-5 py-4.5">
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
      </div>
    </div>
  )
}

function Centered({ icon: Icon, tone, title, children }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-12 text-center text-sm">
      <span className={`inline-flex size-11 items-center justify-center rounded-full ${tone}`}>
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <p className="mt-1 font-display text-[15px] font-bold text-navy">{title}</p>
      {children}
    </div>
  )
}

function Legend({ color, children }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden="true" className={color} />
      {children}
    </span>
  )
}

// The transcript of one interview, read-only, for the interviewer: search
// with every match marked, a timeline of the whole interview and a text
// file to download. Opened from a Completed row of the Interviews tab.
export default function TranscriptPage() {
  const { sessionId } = useParams()
  const [info, setInfo] = useState(null)
  const [turns, setTurns] = useState(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [current, setCurrent] = useState(0)
  // The part of the interview on screen: { fromMs, toMs }.
  const [view, setView] = useState(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    let isCurrent = true
    Promise.all([readInterview(sessionId), readTranscript(sessionId)])
      .then(([interview, transcript]) => {
        if (!isCurrent) return
        setInfo(interview)
        setTurns(transcript.turns)
      })
      .catch((loadError) => isCurrent && setError(loadError.message))
    return () => {
      isCurrent = false
    }
  }, [sessionId])

  const matches = useMemo(() => findMatches(turns ?? [], query), [turns, query])
  const currentMatch = matches[current] ?? null
  const isSearching = query.trim() !== ''
  const showsTurns = turns?.length > 0 && !(isSearching && matches.length === 0)

  // Which turns are on screen, for the box on the timeline.
  const measure = useCallback(() => {
    const box = scrollRef.current
    if (!box) return
    const top = box.scrollTop
    const bottom = top + box.clientHeight
    let range = null
    box.querySelectorAll('[data-turn]').forEach((row) => {
      if (row.offsetTop + row.offsetHeight <= top || row.offsetTop >= bottom) return
      const fromMs = range ? range.fromMs : Number(row.dataset.ms)
      range = { fromMs, toMs: Number(row.dataset.end) }
    })
    setView(range)
  }, [])

  // Measured again whenever the list appears or changes size.
  useEffect(() => {
    const box = scrollRef.current
    if (!box) return undefined
    const observer = new ResizeObserver(() => measure())
    observer.observe(box)
    return () => observer.disconnect()
  }, [measure, showsTurns])

  const scrollToTurn = useCallback((turnId, where) => {
    const box = scrollRef.current
    const row = box?.querySelector(`[data-turn="${turnId}"]`)
    if (!row) return
    const top =
      where === 'center'
        ? row.offsetTop - (box.clientHeight - row.offsetHeight) / 2
        : row.offsetTop - 8
    box.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  }, [])

  // Each new current match is brought to the middle of the list.
  useEffect(() => {
    if (currentMatch) scrollToTurn(currentMatch.turnId, 'center')
  }, [currentMatch, scrollToTurn])

  // The turn being spoken at that moment, or the next one.
  function jumpTo(ms) {
    const turn = turns.findLast((item) => item.start_ms <= ms) ?? turns[0]
    if (turn) scrollToTurn(turn.id, 'start')
  }

  function pickMatch(index) {
    setCurrent(index)
    scrollToTurn(matches[index].turnId, 'center')
  }

  function move(step) {
    if (matches.length === 0) return
    setCurrent((index) => (index + step + matches.length) % matches.length)
  }

  function handleQuery(event) {
    setQuery(event.target.value)
    setCurrent(0)
  }

  function clearSearch() {
    setQuery('')
    setCurrent(0)
  }

  // Enter goes to the next match, Shift + Enter to the one before, and
  // Escape clears the search.
  function handleKeyDown(event) {
    if (event.key === 'Enter') {
      event.preventDefault()
      move(event.shiftKey ? -1 : 1)
    } else if (event.key === 'Escape') {
      clearSearch()
    }
  }

  if (error) {
    return (
      <section className="mx-auto flex max-w-md flex-col items-start gap-4 rounded-card bg-white p-8 shadow-card">
        <CircleAlert className="size-8 text-danger" aria-hidden="true" />
        <h1 className="text-xl font-extrabold tracking-tight">
          The transcript could not be opened
        </h1>
        <p>{error}</p>
        <Button variant="outline" to="/app/jobs">
          Back to Jobs
        </Button>
      </section>
    )
  }
  if (!info || !turns) {
    return (
      <div className="mx-auto max-w-6xl">
        <LoadingTranscript />
      </div>
    )
  }

  const { interview } = info
  const firstName = interview.candidate_name.split(/\s+/)[0]
  const backTo = `/app/jobs/${info.job_id}/interviews`
  const status = STATUSES[interview.status] ?? STATUSES.completed
  const took = tookLabel(interview)

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-sm">
        <Link to="/app/jobs" className="font-semibold text-brand hover:text-brand-dark">
          Jobs
        </Link>
        <span aria-hidden="true">›</span>
        <Link
          to={`/app/jobs/${info.job_id}`}
          className="font-semibold text-brand hover:text-brand-dark"
        >
          {info.job_title}
        </Link>
        <span aria-hidden="true">›</span>
        <Link to={backTo} className="font-semibold text-brand hover:text-brand-dark">
          Interviews
        </Link>
        <span aria-hidden="true">›</span>
        <span className="font-semibold text-navy">Transcript</span>
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <Link
            to={backTo}
            aria-label="Back to Interviews"
            className="inline-flex size-11 shrink-0 items-center justify-center rounded-xl border border-line bg-white text-body hover:bg-tint hover:text-brand"
          >
            <ArrowLeft className="size-5" aria-hidden="true" />
          </Link>
          <div>
            <h1 className="text-[28px] font-extrabold tracking-tight">
              Interview with {interview.candidate_name}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-2.5 text-[14.5px]">
              <span>
                {info.job_title} · {info.job_code}
              </span>
              <span aria-hidden="true">·</span>
              <span>{whenLabel(interview)}</span>
              {took && (
                <>
                  <span aria-hidden="true">·</span>
                  <span>{took}</span>
                </>
              )}
              <StatusChip tone={status.tone}>{status.label}</StatusChip>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <Button
            variant="outline"
            className="disabled:border-line"
            disabled={turns.length === 0}
            onClick={() => downloadText(fileName(info), fileText(info, turns))}
          >
            <Download className="size-4.5" aria-hidden="true" />
            Download .txt
          </Button>
          <span className="text-[12.5px]">Read-only · Only you see this</span>
        </div>
      </header>

      <section
        aria-label="Transcript"
        className="flex h-[calc(100vh-15rem)] min-h-[520px] flex-col overflow-hidden rounded-card border border-line bg-white shadow-card"
      >
        {turns.length === 0 ? (
          <Centered
            icon={CircleAlert}
            tone="bg-danger-soft text-danger"
            title="No transcript for this interview"
          >
            <p className="max-w-md leading-relaxed">
              Transcription was not available while this interview ran, so nothing was written down.
              {interview.status === 'completed' &&
                ' The interview itself is still recorded as completed.'}
            </p>
          </Centered>
        ) : (
          <>
            <div className="flex flex-none flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
              <div className="flex flex-wrap items-center gap-2.5">
                <label htmlFor="transcript-search" className="sr-only">
                  Search the transcript
                </label>
                <div className="relative flex items-center">
                  <Search
                    className="pointer-events-none absolute left-3.5 size-4.5 text-body"
                    aria-hidden="true"
                  />
                  <input
                    id="transcript-search"
                    type="search"
                    value={query}
                    onChange={handleQuery}
                    onKeyDown={handleKeyDown}
                    placeholder="Search the transcript"
                    autoComplete="off"
                    className="min-h-11 w-80 max-w-full rounded-xl border-[1.5px] border-line bg-white pr-10 pl-9.5 text-[14.5px] text-navy placeholder:text-[#8A97AE] focus:border-brand focus:shadow-[0_0_0_3px_#E8F0FF] focus:outline-none [&::-webkit-search-cancel-button]:appearance-none"
                  />
                  {query && (
                    <button
                      type="button"
                      aria-label="Clear the search"
                      onClick={clearSearch}
                      className="absolute right-1.5 inline-flex size-8 items-center justify-center rounded-lg text-body hover:bg-mist"
                    >
                      <X className="size-4" aria-hidden="true" />
                    </button>
                  )}
                </div>
                <span
                  role="status"
                  className={`min-w-16 text-sm font-semibold tabular-nums ${
                    matches.length === 0 ? 'text-danger' : 'text-navy'
                  }`}
                >
                  {isSearching &&
                    (matches.length === 0 ? 'No matches' : `${current + 1} of ${matches.length}`)}
                </span>
                <div className="flex gap-1">
                  <button
                    type="button"
                    aria-label="Previous match"
                    title="Previous match (Shift + Enter)"
                    disabled={matches.length === 0}
                    onClick={() => move(-1)}
                    className={ICON_BUTTON}
                  >
                    <ChevronUp className="size-4.5" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    aria-label="Next match"
                    title="Next match (Enter)"
                    disabled={matches.length === 0}
                    onClick={() => move(1)}
                    className={ICON_BUTTON}
                  >
                    <ChevronDown className="size-4.5" aria-hidden="true" />
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3.5 text-[13.5px]">
                <span>{turns.length} turns</span>
                <Legend color="size-2.5 rounded-[3px] bg-brand">You</Legend>
                <Legend color="size-2.5 rounded-[3px] bg-[#0E7FA6]">{firstName}</Legend>
                <Legend color="h-3 w-[3px] rounded-sm bg-[#D97706]">Match</Legend>
              </div>
            </div>

            {showsTurns ? (
              <>
                <TranscriptTimeline
                  turns={turns}
                  totalMs={Math.max(lengthMs(interview, turns), 1)}
                  firstName={firstName}
                  matches={matches}
                  current={current}
                  view={view}
                  onJump={jumpTo}
                  onPickMatch={pickMatch}
                />
                <div
                  ref={scrollRef}
                  onScroll={measure}
                  className="relative min-h-0 flex-1 overflow-y-auto"
                >
                  <TranscriptTurns
                    turns={turns}
                    candidateName={interview.candidate_name}
                    query={isSearching ? query : ''}
                    currentMatch={currentMatch}
                  />
                </div>
              </>
            ) : (
              <Centered
                icon={Search}
                tone="bg-[#EEF2F9] text-body"
                title={`Nobody said “${query.trim()}” in this interview`}
              >
                <p className="max-w-sm leading-relaxed">
                  Check the spelling or try a shorter word. The full transcript is back when you
                  clear the search.
                </p>
                <Button
                  variant="soft"
                  className="mt-1.5 min-h-10 px-4.5 text-sm"
                  onClick={clearSearch}
                >
                  Clear the search
                </Button>
              </Centered>
            )}
          </>
        )}
      </section>
    </div>
  )
}
