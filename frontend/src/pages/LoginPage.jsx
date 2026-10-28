import {
  ArrowLeft,
  ArrowRight,
  Check,
  CircleAlert,
  Filter,
  Link2,
  LockKeyhole,
  Mail,
  MessageSquare,
  UserRound,
  Video,
} from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router'
import { useAuth } from '../auth/AuthContext.js'
import Button from '../components/Button.jsx'

// Shown one at a time, each for 4 s of a 12 s cycle.
const TRUST_POINTS = [
  { icon: Link2, text: 'Every score links to the CV line or transcript moment behind it.' },
  {
    icon: UserRound,
    text: 'Publishing, invitations, reports and emails wait for your approval.',
  },
  {
    icon: LockKeyhole,
    text: 'Only job-related criteria are scored. Raw audio and video are never stored.',
  },
]

// The hiring journey: each stage lights up in its own colour in turn.
const JOURNEY = [
  { icon: MessageSquare, label: 'Job', color: '#2563eb' },
  { icon: Filter, label: 'Screen', color: '#7c3aed' },
  { icon: Video, label: 'Interview', color: '#059669' },
  { icon: Check, label: 'Decide', color: '#ea580c' },
]

const INPUT_CLASS =
  'h-13 w-full 2xl:h-14 rounded-2xl border-[1.5px] border-line pl-11.5 text-base font-normal text-navy placeholder:text-body/60 focus:border-brand focus:outline-none focus:ring-4 focus:ring-[#dce8ff]'

function delay(seconds) {
  return { animationDelay: `${seconds}s` }
}

function TrustPoints() {
  return (
    <div className="flex flex-col gap-4">
      <ul className="relative h-19 motion-reduce:flex motion-reduce:h-auto motion-reduce:flex-col motion-reduce:gap-3">
        {TRUST_POINTS.map(({ icon: Icon, text }, index) => (
          <li
            key={text}
            className="absolute inset-0 flex animate-tour-panel items-start gap-3 text-[19px] leading-normal text-[#e3ecff] opacity-0 motion-reduce:static motion-reduce:opacity-100"
            style={delay(index * 4)}
          >
            <Icon className="mt-0.5 size-6 shrink-0 text-[#a9c8ff]" aria-hidden="true" />
            {text}
          </li>
        ))}
      </ul>
      <div className="flex gap-2 motion-reduce:hidden" aria-hidden="true">
        {TRUST_POINTS.map((point, index) => (
          <span
            key={point.text}
            className="h-2 w-2 animate-cycle-dot rounded-full bg-white/35"
            style={delay(index * 4)}
          />
        ))}
      </div>
    </div>
  )
}

function HiringJourney() {
  return (
    <div aria-hidden="true" className="relative hidden w-100 justify-between pt-1 sm:flex">
      <div className="absolute inset-x-9.5 top-7.75 h-0.75 rounded-full bg-white/20" />
      <div className="absolute inset-x-9.5 top-7.75 h-0.75 animate-journey-track rounded-full bg-linear-to-r from-[#93c5fd] via-[#c4b5fd] via-60% to-[#fdba74]" />
      <span className="absolute left-7.75 top-6.25 z-2 size-3.75 animate-journey-travel rounded-full bg-white shadow-[0_0_0_5px_rgb(255_255_255/0.25),0_0_18px_#fff]" />
      {JOURNEY.map(({ icon: Icon, label, color }, index) => (
        <div key={label} className="relative z-1 flex w-19 flex-col items-center gap-2.5">
          <span
            className="flex size-13.5 animate-journey-stage items-center justify-center rounded-[17px] border border-white/30 bg-white/12"
            style={{ '--stage-color': color, ...delay(index * 2) }}
          >
            <Icon className="size-6 text-white" />
          </span>
          <span className="text-[13px] font-bold text-[#e3ecff]">{label}</span>
        </div>
      ))}
    </div>
  )
}

function BrandPanel() {
  return (
    <section className="relative flex flex-1 basis-120 flex-col justify-between gap-12 overflow-hidden bg-linear-140 from-royal via-brand via-70% to-[#3b74ea] px-8 py-10 md:px-14 md:py-12">
      {/* Soft light drifting behind the content, and light rings. */}
      <div
        aria-hidden="true"
        className="absolute -right-40 -top-40 size-130 animate-glow-drift rounded-full bg-[radial-gradient(circle,rgb(169_200_255/0.4)_0%,transparent_66%)]"
      />
      <div
        aria-hidden="true"
        className="absolute -bottom-42 -left-42 size-115 animate-glow-drift-back rounded-full bg-[radial-gradient(circle,rgb(167_139_250/0.35)_0%,transparent_66%)]"
      />
      <svg viewBox="0 0 620 620" aria-hidden="true" className="absolute -bottom-50 -right-45 w-155">
        <g fill="none" stroke="#fff" strokeOpacity="0.1">
          {[110, 170, 230, 290].map((radius) => (
            <circle key={radius} cx="310" cy="310" r={radius} />
          ))}
        </g>
      </svg>
      <Link to="/" className="relative flex items-center gap-3" aria-label="HireLucent home">
        <span className="flex size-10.5 items-center justify-center rounded-[13px] bg-white">
          <img src="/favicon.svg" alt="" className="size-7" />
        </span>
        <span className="font-display text-2xl font-extrabold tracking-tight text-white">
          HireLucent
        </span>
      </Link>
      <div className="relative flex max-w-lg flex-col gap-7.5">
        <p className="animate-rise-up font-display text-3xl font-extrabold leading-tight tracking-tight text-white md:text-[46px]">
          Hire with clarity.
          <br />
          Decide with evidence.
        </p>
        <TrustPoints />
        <HiringJourney />
      </div>
      <p className="relative text-sm font-semibold text-[#c9d8fb]">AI assists. People decide.</p>
    </section>
  )
}

export default function LoginPage() {
  const { user, login } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Already signed in: go to the page that was asked for, or the dashboard.
  if (user) return <Navigate to={location.state?.from ?? '/app'} replace />

  async function handleSubmit(event) {
    event.preventDefault()
    setErrorMessage('')
    setIsSubmitting(true)
    try {
      await login(email, password)
    } catch (error) {
      setErrorMessage(error.message)
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-wrap bg-mist">
      <BrandPanel />
      <main className="flex flex-1 basis-120 items-center justify-center px-6 py-12">
        <form
          onSubmit={handleSubmit}
          className="flex w-full max-w-110 animate-rise-up flex-col gap-5 rounded-[28px] border border-line bg-white p-8 shadow-[0_30px_70px_rgb(11_31_75/0.12)] md:p-10 2xl:max-w-130 2xl:gap-6 2xl:p-12"
          style={delay(0.15)}
        >
          <div className="flex flex-col gap-2">
            <span className="inline-flex items-center gap-2 text-[13px] font-bold uppercase tracking-widest text-brand">
              <span className="h-0.75 w-6 rounded-full bg-brand" aria-hidden="true" />
              Interviewer access
            </span>
            <h1 className="text-[32px] font-extrabold tracking-tight 2xl:text-[38px]">
              Welcome back
            </h1>
            <p className="text-base">Sign in to your workspace to continue hiring.</p>
          </div>

          {errorMessage && (
            <p
              role="alert"
              className="flex animate-shake items-center gap-2.5 rounded-2xl bg-danger-soft px-4 py-3.5 text-[15px] font-semibold text-danger"
            >
              <CircleAlert className="size-5 shrink-0" aria-hidden="true" />
              {errorMessage}
            </p>
          )}

          <label className="flex flex-col gap-2 text-sm font-bold text-navy">
            Email
            <span className="relative flex items-center">
              <Mail className="absolute left-4 size-4.5 text-brand" aria-hidden="true" />
              <input
                type="email"
                required
                autoComplete="username"
                placeholder="you@company.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className={INPUT_CLASS}
              />
            </span>
          </label>

          <label className="flex flex-col gap-2 text-sm font-bold text-navy">
            Password
            <span className="relative flex items-center">
              <LockKeyhole className="absolute left-4 size-4.5 text-body" aria-hidden="true" />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className={`${INPUT_CLASS} pr-21`}
              />
              <button
                type="button"
                aria-pressed={showPassword}
                onClick={() => setShowPassword((shown) => !shown)}
                className="absolute right-1.5 h-10 rounded-xl bg-tint px-3.5 text-sm font-bold text-brand hover:bg-lavender"
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </span>
          </label>

          <Button type="submit" disabled={isSubmitting} className="min-h-13.5 text-base">
            {isSubmitting ? (
              'Signing in…'
            ) : (
              <>
                Sign in <ArrowRight className="size-4.5" aria-hidden="true" />
              </>
            )}
          </Button>

          <div className="flex items-start gap-3 rounded-2xl bg-mist px-4 py-3.5">
            <Video className="mt-0.5 size-5 shrink-0 text-[#059669]" aria-hidden="true" />
            <p className="text-sm leading-relaxed">
              <b className="text-navy">Joining as a candidate?</b> You do not need an account. Use
              the private link in your interview invitation.
            </p>
          </div>
          <Link
            to="/"
            className="inline-flex items-center gap-2 self-start text-sm font-bold text-brand hover:text-brand-dark"
          >
            <ArrowLeft className="size-4" aria-hidden="true" /> Back to home
          </Link>
        </form>
      </main>
    </div>
  )
}
