import { CalendarDays, CircleCheck, Clock3, UserRound } from 'lucide-react'
import { useState } from 'react'
import { browserZoneLabel, clock, longDay, span } from '../../lib/interviews.js'
import { timeUntil } from '../../lib/join.js'
import Button from '../Button.jsx'
import CandidateLayout from './CandidateLayout.jsx'
import DeviceChecks from './DeviceChecks.jsx'
import DevicePreview from './DevicePreview.jsx'

function Detail({ icon: Icon, title, children }) {
  return (
    <span className="flex items-start gap-3 text-[15px] text-navy">
      <Icon className="mt-px size-5 shrink-0 text-brand" aria-hidden="true" />
      <span>
        <strong className="font-semibold">{title}</strong>
        <span className="block text-body">{children}</span>
      </span>
    </span>
  )
}

// When Join opens, or that it is open now.
function JoinWindow({ link, isOpen, now }) {
  if (isOpen) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-success-soft px-4 py-3.5 text-success">
        <span className="flex items-center gap-2 text-[15px] font-semibold">
          <CircleCheck className="size-4.5" aria-hidden="true" />
          Join is open
        </span>
        <span className="text-sm">The interview starts at {clock(link.scheduled_start)}</span>
      </div>
    )
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-amber-soft px-4 py-3.5 text-amber">
      <span className="flex items-center gap-2 text-[15px] font-semibold">
        <Clock3 className="size-4.5" aria-hidden="true" />
        Join opens at {clock(link.opens_at)}
      </span>
      <span className="text-sm">{timeUntil(link.opens_at, now)}</span>
    </div>
  )
}

// The page a candidate sees when they open their link: check the camera
// and microphone, agree to the transcript (and, with a PIN, to the identity
// photo), and join when Join opens.
export default function PreJoin({ link, preview, now, isBusy, error, onJoin }) {
  const [hasConsent, setHasConsent] = useState(false)
  // Join opens on the clock, even before the next check with the server.
  const isOpen = link.state === 'open' || now >= new Date(link.opens_at)
  const canJoin = isOpen && hasConsent && !isBusy
  const greeting = link.first_name ? `Hi ${link.first_name}, check` : 'Check'

  return (
    <CandidateLayout note="Interview invitation">
      <div>
        <h1 className="text-[34px] font-extrabold tracking-tight text-balance">
          Your interview for {link.job_title}
        </h1>
        <p className="mt-2.5 text-[17px]">
          {greeting} your camera and microphone here. You can join from{' '}
          {Math.round((new Date(link.scheduled_start) - new Date(link.opens_at)) / 60000)} minutes
          before the start.
        </p>
      </div>

      <div className="grid items-start gap-7 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-3.5">
          <DevicePreview preview={preview} showSelects />
          <DeviceChecks preview={preview} />
        </div>

        <section
          aria-label="Interview details"
          className="flex min-w-0 flex-col gap-5 rounded-card border border-line bg-white p-6.5 shadow-card"
        >
          <div className="flex flex-col gap-3">
            <Detail icon={CalendarDays} title={longDay(link.scheduled_start)}>
              {span(link.scheduled_start, link.scheduled_end)}, your time ({browserZoneLabel()})
            </Detail>
            <Detail icon={UserRound} title="One-to-one video interview">
              With the HireLucent hiring team · about {link.length_minutes} minutes
            </Detail>
          </div>

          <JoinWindow link={link} isOpen={isOpen} now={now} />

          <label className="flex items-start gap-3 rounded-2xl border-[1.5px] border-line px-4 py-3.5 text-[14.5px] leading-normal text-navy">
            <input
              type="checkbox"
              checked={hasConsent}
              onChange={(event) => setHasConsent(event.target.checked)}
              className="mt-0.5 size-4.5 shrink-0 accent-brand"
            />
            <span>
              {link.pin_required
                ? 'I agree that what is said in this interview is turned into a written transcript for the hiring team, and that one photo is taken to confirm it is me. The photo is compared with my application photo and deleted straight away. The audio and video are not recorded or kept.'
                : 'I agree that what is said in this interview is turned into a written transcript for the hiring team. The audio and video are not recorded or kept.'}
            </span>
          </label>

          <Button className="min-h-13 text-base" disabled={!canJoin} onClick={onJoin}>
            {isBusy ? 'Joining…' : link.pin_required ? 'Continue' : 'Join interview'}
          </Button>
          {error ? (
            <p role="alert" className="-mt-2 text-center text-sm font-semibold text-danger">
              {error}
            </p>
          ) : (
            !isBusy &&
            (!canJoin ? (
              <p className="-mt-2 text-center text-[13.5px]">
                {isOpen
                  ? 'Tick the box above to join.'
                  : `Available from ${clock(link.opens_at)}, after you agree above.`}
              </p>
            ) : (
              link.pin_required && (
                <p className="-mt-2 text-center text-[13.5px]">
                  Next: one quick photo, then the waiting room.
                </p>
              )
            ))
          )}

          <div className="flex flex-col gap-2 border-t border-line/60 pt-4 text-sm">
            <span className="font-semibold text-navy">Before you start</span>
            <span>Find a quiet place and use headphones if you can.</span>
            <span>
              If your connection drops, open your invitation link again. You will come back to
              the same interview.
            </span>
          </div>
        </section>
      </div>
    </CandidateLayout>
  )
}
