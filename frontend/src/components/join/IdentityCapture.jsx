import {
  Camera,
  Check,
  LoaderCircle,
  RotateCcw,
  ScanFace,
  ShieldCheck,
  Trash2,
  TriangleAlert,
  Video,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useFaceGuide } from '../../hooks/useFaceGuide.js'
import { faceCrop, GREEN_SECONDS, OVAL, TIPS } from '../../lib/faceGuide.js'
import { sendIdentityPhoto, skipIdentityPhoto } from '../../lib/join.js'
import Button from '../Button.jsx'
import CandidateLayout from './CandidateLayout.jsx'

const STEPS = [
  { label: 'PIN', state: 'done' },
  { label: 'Camera and consent', state: 'done' },
  { label: 'Photo', state: 'current' },
  { label: 'Waiting room', state: 'next' },
]
const STEP_STYLES = {
  done: 'bg-success-soft text-success',
  current: 'bg-tint text-brand',
  next: 'bg-[#eef1f6] text-[#44526b]',
}

function Steps() {
  return (
    <ol aria-label="Steps" className="flex flex-wrap gap-2.5 text-[13.5px] font-semibold">
      {STEPS.map((step) => (
        <li
          key={step.label}
          aria-current={step.state === 'current' ? 'step' : undefined}
          className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 ${STEP_STYLES[step.state]}`}
        >
          {step.state === 'done' && <Check className="size-3.5" aria-hidden="true" />}
          {step.state === 'current' && <Camera className="size-3.5" aria-hidden="true" />}
          {step.label}
        </li>
      ))}
    </ol>
  )
}

// The oval the face goes in, with the rest of the picture dimmed. Green
// when every check passes, dashed amber while a tip is shown.
function Oval({ tone }) {
  const stroke = { good: '#34d399', warn: '#fbbf24', idle: 'rgba(255,255,255,0.75)' }[tone]
  const cx = OVAL.x * 400
  const cy = OVAL.y * 250
  const rx = (OVAL.width * 400) / 2
  const ry = (OVAL.height * 250) / 2
  return (
    <svg
      viewBox="0 0 400 250"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 size-full"
    >
      <path
        d={`M0 0H400V250H0Z M${cx} ${cy - ry}a${rx} ${ry} 0 1 0 0.1 0Z`}
        fill="rgba(5,12,30,0.55)"
        fillRule="evenodd"
      />
      <ellipse
        cx={cx}
        cy={cy}
        rx={rx}
        ry={ry}
        fill="none"
        stroke={stroke}
        strokeWidth="4"
        strokeDasharray={tone === 'good' ? undefined : '10 8'}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

function TipChip({ tone, children }) {
  const style = {
    good: 'bg-success/90',
    warn: 'bg-warning/90',
    idle: 'bg-navy/80',
  }[tone]
  return (
    <span
      role="status"
      className={`absolute left-1/2 top-3.5 inline-flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full px-3.5 py-2 text-sm font-semibold text-white ${style}`}
    >
      {tone === 'good' && <Check className="size-4" aria-hidden="true" />}
      {tone === 'warn' && <TriangleAlert className="size-4" aria-hidden="true" />}
      {children}
    </span>
  )
}

const HOW_IT_WORKS = [
  {
    key: 'oval',
    icon: ScanFace,
    text: (
      <>
        Put your face inside the oval and follow the tips. The border turns <strong>green</strong>{' '}
        when it is right.
      </>
    ),
  },
  {
    key: 'auto',
    icon: Camera,
    text: (
      <>
        The photo is taken by itself after {GREEN_SECONDS} seconds of green, or press{' '}
        <strong>Take photo</strong>.
      </>
    ),
  },
  {
    key: 'deleted',
    icon: Trash2,
    text: (
      <>
        It is compared with the photo from your application, then <strong>deleted</strong>. It is
        never stored.
      </>
    ),
  },
  {
    key: 'join',
    icon: Video,
    text: 'You join the waiting room either way. The check never stops you from joining.',
  },
]

function HowItWorks() {
  return (
    <section
      aria-labelledby="how-title"
      className="flex min-w-0 flex-col gap-4.5 rounded-card border border-line bg-white p-6.5 shadow-card"
    >
      <h2 id="how-title" className="text-xl font-extrabold">
        How it works
      </h2>
      <ul className="flex flex-col gap-3.5 text-[14.5px] leading-normal text-navy">
        {HOW_IT_WORKS.map(({ key, icon: Icon, text }) => (
          <li key={key} className="flex items-start gap-3">
            <span className="flex size-8.5 shrink-0 items-center justify-center rounded-[11px] bg-tint text-brand">
              <Icon className="size-4.25" aria-hidden="true" />
            </span>
            <span>{text}</span>
          </li>
        ))}
      </ul>
      <p className="flex items-start gap-2.5 rounded-2xl bg-teal-soft px-3.5 py-3 text-sm leading-normal text-teal">
        <ShieldCheck className="mt-px size-4.5 shrink-0" aria-hidden="true" />
        The face guide runs in your browser. Only the one photo is sent, over a secure connection.
      </p>
    </section>
  )
}

// A face found longer ago than this is not used for cutting out the photo.
const FACE_MAX_AGE_MS = 1000

// One JPEG of the camera picture as it is now. With a face from the guide,
// only the area around that face is kept, so nobody else in the room is
// sent; without one (no live tips), the whole picture is sent and the
// server ignores small faces far behind.
function takePhoto(video, face) {
  const isRecent = face && Date.now() - face.foundAt <= FACE_MAX_AGE_MS
  const area = isRecent
    ? faceCrop(face, video.videoWidth, video.videoHeight)
    : { x: 0, y: 0, width: video.videoWidth, height: video.videoHeight }
  const canvas = document.createElement('canvas')
  canvas.width = area.width
  canvas.height = area.height
  canvas
    .getContext('2d')
    .drawImage(video, area.x, area.y, area.width, area.height, 0, 0, area.width, area.height)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
}

// The identity photo step (F7), after Join and before the waiting room.
// The candidate is only ever told "done", "try again" or "continue";
// never how well the photo matched. onDone("taken" | "skipped").
export default function IdentityCapture({ link, preview, pass, onDone, onEnded }) {
  const videoRef = useRef(null)
  const hasCamera = Boolean(preview.stream?.getVideoTracks().length) && preview.cameraOn
  const guide = useFaceGuide(videoRef, hasCamera)
  const { faceRef } = guide
  const [now, setNow] = useState(() => Date.now())
  // "ready", "sending", "retry" (with triesLeft) or "gave_up".
  const [phase, setPhase] = useState('ready')
  const [triesLeft, setTriesLeft] = useState(null)
  const [error, setError] = useState('')
  const [isSkipping, setIsSkipping] = useState(false)
  // When the last unusable photo came back. The green countdown starts again
  // from then, so a retry is never taken straight away.
  const [retryAt, setRetryAt] = useState(0)

  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = preview.stream
  }, [preview.stream, hasCamera])

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(timer)
  }, [])

  const isGuided = guide.status === 'ready'
  const isWaiting = phase === 'ready' || phase === 'retry'
  const isGreen = isGuided && guide.tip === 'good'
  const greenSince = isGreen && guide.greenSince ? Math.max(guide.greenSince, retryAt) : null
  const greenFor = greenSince ? Math.max(0, now - greenSince) / 1000 : 0
  const countdown = isGreen ? Math.max(1, Math.ceil(GREEN_SECONDS - greenFor)) : null
  const canTake = hasCamera && phase !== 'sending' && phase !== 'gave_up' && (isGreen || !isGuided)

  const send = useCallback(async () => {
    const video = videoRef.current
    if (!video?.videoWidth) return
    setPhase('sending')
    setError('')
    try {
      const photo = await takePhoto(video, faceRef.current)
      const answer = await sendIdentityPhoto(pass, photo)
      if (answer.state === 'done') onDone('taken')
      else if (answer.state === 'skipped') setPhase('gave_up')
      else {
        setTriesLeft(answer.tries_left)
        setRetryAt(Date.now())
        setPhase('retry')
      }
    } catch (sendError) {
      if (sendError.status === 401 || sendError.status === 404) {
        onEnded()
        return
      }
      setError(sendError.message)
      setPhase('ready')
    }
  }, [pass, faceRef, onDone, onEnded])

  // Take the photo by itself after five seconds of green.
  useEffect(() => {
    if (!isWaiting || !greenSince) return undefined
    const wait = Math.max(0, GREEN_SECONDS * 1000 - (Date.now() - greenSince))
    const timer = setTimeout(send, wait)
    return () => clearTimeout(timer)
  }, [isWaiting, greenSince, send])

  async function handleSkip(reason) {
    setIsSkipping(true)
    try {
      await skipIdentityPhoto(pass, reason)
    } catch (skipError) {
      if (skipError.status === 401 || skipError.status === 404) {
        onEnded()
        return
      }
    }
    onDone('skipped')
  }

  let tone = 'idle'
  let tipText = TIPS.starting
  if (phase === 'sending') tipText = 'Checking the photo…'
  else if (isGuided) {
    tone = isGreen ? 'good' : 'warn'
    tipText = TIPS[guide.tip]
  } else if (guide.status === 'unavailable')
    tipText = 'Fill the oval with your face, then take the photo'

  const greeting = link.first_name ? `Hi ${link.first_name}, one` : 'One'

  return (
    <CandidateLayout note={`Interview for ${link.job_title}`}>
      <Steps />
      <div className="flex flex-col gap-2">
        <h1 className="text-[34px] font-extrabold tracking-tight text-balance">Confirm it’s you</h1>
        <p className="text-[17px]">{greeting} quick photo before the waiting room.</p>
      </div>

      <div className="grid items-start gap-7 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
        <section aria-label="Photo" className="flex min-w-0 flex-col gap-3.5">
          <div className="relative aspect-[16/10] w-full overflow-hidden rounded-card bg-[#16233f]">
            {hasCamera ? (
              <>
                <video
                  ref={videoRef}
                  autoPlay
                  muted
                  playsInline
                  aria-label="Your camera preview"
                  className="size-full -scale-x-100 object-cover"
                />
                <Oval tone={phase === 'sending' ? 'idle' : tone} />
                <TipChip tone={phase === 'sending' ? 'idle' : tone}>{tipText}</TipChip>
                {countdown && isWaiting && (
                  <span
                    aria-label={`Photo in ${countdown} seconds`}
                    className="absolute bottom-4 right-4 flex size-14.5 items-center justify-center rounded-full border-[3px] border-[#34d399] bg-navy/80 font-display text-2xl font-extrabold text-white"
                  >
                    {countdown}
                  </span>
                )}
                {phase === 'sending' && (
                  <LoaderCircle
                    className="absolute bottom-4 right-4 size-10 animate-spin text-white motion-reduce:animate-none"
                    aria-hidden="true"
                  />
                )}
              </>
            ) : (
              <p className="absolute inset-x-6 top-1/2 -translate-y-1/2 text-center text-[15px] font-semibold text-white/85">
                {preview.error || 'Your camera is off. Turn it on to take the photo.'}
              </p>
            )}
          </div>

          {phase === 'retry' && (
            <p
              role="alert"
              className="flex items-start gap-2.5 rounded-2xl bg-amber-soft px-3.5 py-3 text-sm leading-normal text-amber"
            >
              <RotateCcw className="mt-px size-4.5 shrink-0" aria-hidden="true" />
              <span>
                We couldn’t use that photo. Make sure your face is well lit and fills the oval, then
                try again.{' '}
                <strong>{triesLeft === 1 ? '1 try left.' : `${triesLeft} tries left.`}</strong>
              </span>
            </p>
          )}
          {error && (
            <p role="alert" className="text-sm font-semibold text-danger">
              {error}
            </p>
          )}

          {phase === 'gave_up' || !hasCamera ? (
            <div className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-white p-4.5">
              <p className="text-[14.5px] leading-normal text-navy">
                {hasCamera
                  ? 'We couldn’t take a clear photo. That’s fine: you can still join.'
                  : 'You can join without the photo.'}{' '}
                The hiring team may ask to see a photo ID at the start.
              </p>
              <Button
                disabled={isSkipping}
                onClick={() => (phase === 'gave_up' ? onDone('skipped') : handleSkip('no_camera'))}
              >
                {isSkipping ? 'Continuing…' : 'Continue to the waiting room'}
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <Button className="min-h-13 px-7 text-base" disabled={!canTake} onClick={send}>
                <Camera className="size-4.5" aria-hidden="true" />
                {phase === 'sending' ? 'Checking…' : phase === 'retry' ? 'Try again' : 'Take photo'}
              </Button>
              <span className="text-sm" aria-live="polite">
                {countdown && isWaiting
                  ? `Taking the photo in ${countdown} seconds…`
                  : isGuided && phase !== 'sending'
                    ? 'Take photo turns on when the border is green.'
                    : ''}
              </span>
            </div>
          )}
        </section>

        <HowItWorks />
      </div>
    </CandidateLayout>
  )
}
