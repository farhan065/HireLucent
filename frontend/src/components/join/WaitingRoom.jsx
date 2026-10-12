import { Check, Clock3 } from 'lucide-react'
import { clock } from '../../lib/interviews.js'
import { timeUntil } from '../../lib/join.js'
import Button from '../Button.jsx'
import CandidateLayout from './CandidateLayout.jsx'
import DevicePreview from './DevicePreview.jsx'

function startsLabel(start, now) {
  const until = timeUntil(start, now)
  return `${clock(start)} your time · ${until === 'now' ? 'starting now' : until}`
}

function ReadyCheck({ isOk, children }) {
  return (
    <li className={`flex items-center gap-2.5 ${isOk ? 'text-navy' : 'text-body'}`}>
      <Check
        className={`size-4.5 shrink-0 ${isOk ? 'text-success' : 'text-line'}`}
        aria-hidden="true"
      />
      {children}
    </li>
  )
}

// Where the candidate waits after joining, until the interviewer lets them
// in. Their camera and microphone stay ready.
export default function WaitingRoom({ link, preview, now, isLeaving, onLeave }) {
  return (
    <CandidateLayout note={`Interview for ${link.job_title}`}>
      <div className="grid items-start gap-7 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <DevicePreview
          preview={preview}
          note="Your camera and microphone stay ready while you wait."
        />

        <section
          aria-labelledby="waiting-title"
          className="flex min-w-0 flex-col gap-5 rounded-card border border-line bg-white p-7.5 shadow-card"
        >
          <div className="flex items-center gap-3.5">
            <span
              aria-hidden="true"
              className="relative flex size-13 shrink-0 items-center justify-center rounded-full bg-tint"
            >
              <span className="absolute -inset-1.5 animate-pulse rounded-full border-2 border-brand/30" />
              <Clock3 className="size-6 text-brand" />
            </span>
            <div>
              <h1 id="waiting-title" className="text-[26px] font-extrabold tracking-tight">
                You are in the waiting room
              </h1>
              <p className="mt-1.5 text-[15.5px]" role="status">
                The interviewer will let you in shortly.
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-1.5 rounded-2xl bg-mist px-4 py-3.5 text-[14.5px]">
            <span className="flex justify-between gap-3">
              <span>Starts</span>
              <strong className="text-right font-semibold text-navy">
                {startsLabel(link.scheduled_start, now)}
              </strong>
            </span>
            <span className="flex justify-between gap-3">
              <span>Length</span>
              <strong className="font-semibold text-navy">
                About {link.length_minutes} minutes
              </strong>
            </span>
          </div>

          <ul aria-label="Ready checks" className="flex flex-col gap-2.5 text-[14.5px]">
            <ReadyCheck isOk={preview.cameraWorks}>
              {preview.cameraWorks ? 'Camera working' : 'Camera off'}
            </ReadyCheck>
            <ReadyCheck isOk={preview.microphoneWorks}>
              {preview.microphoneWorks
                ? 'Microphone working'
                : 'Microphone not heard yet: say something'}
            </ReadyCheck>
            <ReadyCheck isOk>You agreed to the written transcript</ReadyCheck>
          </ul>

          <p className="rounded-2xl bg-amber-soft px-3.5 py-3 text-sm leading-normal text-amber">
            Keep this tab open. When the interviewer lets you in, the interview opens here by
            itself.
          </p>

          <Button
            variant="outline"
            className="self-start border-line text-navy hover:bg-mist"
            disabled={isLeaving}
            onClick={onLeave}
          >
            {isLeaving ? 'Leaving…' : 'Leave the waiting room'}
          </Button>
        </section>
      </div>
    </CandidateLayout>
  )
}
