import { AppWindow, RefreshCw, WifiOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { elapsed } from '../../lib/room.js'

// After this long without a connection, the card offers to try again now.
const STILL_TRYING_MS = 30 * 1000
const BUTTON =
  'inline-flex min-h-10 items-center justify-center rounded-full px-4 font-display text-[13.5px] font-bold'

function useNow() {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  return now
}

function Card({ icon: Icon, iconClassName, title, children }) {
  return (
    <div
      role="status"
      className="absolute left-1/2 top-[46%] flex w-[min(88%,380px)] -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-2.25 rounded-[20px] bg-white px-6 py-5.5 text-center shadow-[0_24px_60px_rgb(11_31_75/0.3)]"
    >
      <Icon className={`size-9 ${iconClassName}`} aria-hidden="true" />
      <span className="font-display text-lg font-extrabold text-navy">{title}</span>
      {children}
    </div>
  )
}

function Lost({ lostAt, onRetry }) {
  const now = useNow()
  const timer = (
    <span className="text-[13px] tabular-nums">Disconnected for {elapsed(lostAt, now)}</span>
  )
  if (now - lostAt < STILL_TRYING_MS) {
    return (
      <Card icon={RefreshCw} iconClassName="text-brand" title="Reconnecting…">
        <span className="text-sm leading-normal">
          Your connection dropped. The interview is still running and you will be back in a
          moment. Keep this tab open.
        </span>
        {timer}
      </Card>
    )
  }
  return (
    <Card icon={WifiOff} iconClassName="text-amber" title="Still trying to reconnect">
      <span className="text-sm leading-normal">
        Check your Wi-Fi or network cable. The interview is still running; you will rejoin as soon
        as the connection is back.
      </span>
      {timer}
      <span className="mt-1 flex flex-wrap justify-center gap-2.5">
        <button type="button" onClick={onRetry} className={`${BUTTON} bg-brand text-white hover:bg-brand-dark`}>
          Try again now
        </button>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className={`${BUTTON} border-[1.5px] border-line bg-white text-navy hover:bg-mist`}
        >
          Reload page
        </button>
      </span>
    </Card>
  )
}

// Over the video while this person's connection is lost, or when the same
// interview was opened in another tab and this one was disconnected.
export default function ConnectionOverlay({ room }) {
  if (!room.isReplaced && !room.lostAt) return null
  return (
    <>
      <div aria-hidden="true" className="absolute inset-0 bg-navy/60" />
      {room.isReplaced ? (
        <Card icon={AppWindow} iconClassName="text-brand" title="Open in another tab">
          <span className="text-sm leading-normal">
            This interview is open in another tab or on another device, so this tab was
            disconnected.
          </span>
          <button
            type="button"
            onClick={room.rejoin}
            className={`${BUTTON} mt-1 bg-brand px-4.5 text-white hover:bg-brand-dark`}
          >
            Use this tab instead
          </button>
        </Card>
      ) : (
        <Lost lostAt={room.lostAt} onRetry={room.rejoin} />
      )}
    </>
  )
}

// In the other person's place while their connection is dropped.
export function RemoteDropped({ name, initials, since }) {
  const now = useNow()
  return (
    <div className="flex size-full flex-col items-center justify-center gap-2.5 px-6 pb-12 text-center text-white">
      <span className="flex size-21 items-center justify-center rounded-full bg-white/10 font-display text-[28px] font-bold text-white/75">
        {initials}
      </span>
      <span className="rounded-full bg-amber-soft px-2.75 py-1 text-[12.5px] font-bold text-amber">
        Connection dropped
      </span>
      <span className="text-[15px] font-semibold">{name.title} connection dropped</span>
      <span className="max-w-[min(100%,24rem)] text-[13.5px] leading-normal text-white/80">
        The interview is still running. Waiting for {name.waiting} to come back…{' '}
        <span className="tabular-nums">{elapsed(since, now)}</span>
      </span>
    </div>
  )
}
