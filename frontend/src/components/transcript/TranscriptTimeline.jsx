import { fromStart } from '../../lib/room.js'

const MINUTE_MS = 60 * 1000
// The thinnest a turn is drawn, so short answers stay visible.
const MIN_WIDTH = 0.15

function percent(ms, totalMs) {
  return `${Math.min(100, Math.max(0, (ms / totalMs) * 100))}%`
}

// Markers every 5 minutes, or every minute for a short interview.
function minuteMarks(totalMs) {
  const step = totalMs < 10 * MINUTE_MS ? MINUTE_MS : 5 * MINUTE_MS
  const marks = []
  for (let ms = 0; ms <= totalMs; ms += step) marks.push(ms)
  return marks
}

// The whole interview in one strip: when each person spoke, where the
// search matches are and which part is on screen. Clicking the strip, a
// minute marker or a match jumps there.
export default function TranscriptTimeline({
  turns,
  totalMs,
  firstName,
  matches,
  current,
  view,
  onJump,
  onPickMatch,
}) {
  function handleStripClick(event) {
    const box = event.currentTarget.getBoundingClientRect()
    onJump(((event.clientX - box.left) / box.width) * totalMs)
  }

  return (
    <div className="flex-none border-b border-line bg-[#FBFDFF] px-5 pt-3.5 pb-1.5">
      <div className="grid grid-cols-[52px_minmax(0,1fr)] items-center gap-2.5">
        <div className="flex flex-col gap-1.5 text-xs font-semibold text-navy" aria-hidden="true">
          <span className="h-3 leading-3">You</span>
          <span className="h-3 truncate leading-3">{firstName}</span>
        </div>
        <div className="relative h-[42px]">
          {view && (
            <span
              aria-hidden="true"
              className="absolute -inset-y-1.5 rounded-md border-[1.5px] border-[#A9C8FF] bg-tint"
              style={{
                left: percent(view.fromMs, totalMs),
                width: percent(Math.max(view.toMs - view.fromMs, 0), totalMs),
              }}
            />
          )}
          {/* Keyboard users jump with the minute markers below instead. */}
          <button
            type="button"
            tabIndex={-1}
            aria-hidden="true"
            onClick={handleStripClick}
            className="absolute inset-0 cursor-pointer"
          >
            <span className="absolute inset-x-0 top-[3px] h-3 rounded bg-[#F0F4FA]/80" />
            <span className="absolute inset-x-0 top-[21px] h-3 rounded bg-[#F0F4FA]/80" />
            {turns.map((turn) => (
              <span
                key={turn.id}
                className={`absolute h-3 rounded-[3px] ${
                  turn.speaker === 'interviewer' ? 'top-[3px] bg-brand' : 'top-[21px] bg-[#0E7FA6]'
                }`}
                style={{
                  left: percent(turn.start_ms, totalMs),
                  width: `max(${percent(turn.end_ms - turn.start_ms, totalMs)}, ${MIN_WIDTH}%)`,
                }}
              />
            ))}
          </button>
          {matches.map((match, index) => {
            const isCurrent = index === current
            const label = `Match ${index + 1} at ${fromStart(match.startMs)}`
            return (
              <button
                key={`${match.turnId}-${match.at}`}
                type="button"
                aria-label={label}
                title={label}
                onClick={() => onPickMatch(index)}
                className="absolute -top-1 flex h-[50px] w-3.5 -translate-x-1/2 justify-center"
                style={{ left: percent(match.startMs, totalMs) }}
              >
                <span
                  className={`h-full rounded-sm ${isCurrent ? 'w-1 bg-[#B45309]' : 'w-[3px] bg-[#F0A43A]'}`}
                />
              </button>
            )
          })}
        </div>
      </div>
      <div className="grid grid-cols-[52px_minmax(0,1fr)] gap-2.5">
        <span />
        <div className="relative h-[30px]">
          {minuteMarks(totalMs).map((ms) => (
            <button
              key={ms}
              type="button"
              aria-label={`Jump to ${fromStart(ms)}`}
              onClick={() => onJump(ms)}
              className="absolute top-0.5 flex h-[26px] min-w-10 -translate-x-1/2 flex-col items-center rounded-md px-1 text-xs tabular-nums hover:bg-tint hover:text-brand-dark"
              style={{ left: percent(ms, totalMs) }}
            >
              <span aria-hidden="true" className="h-[5px] w-px bg-[#B7C3D8]" />
              {fromStart(ms)}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
