import { ArrowLeft, CircleAlert, CircleCheck } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router'
import { useAuth } from '../auth/AuthContext.js'
import Button from '../components/Button.jsx'

const TRUST_POINTS = [
  'Every score links to the CV line or transcript moment behind it.',
  'Publishing, invitations and reports wait for your approval.',
  'Only job-related criteria are scored.',
]

const INPUT_CLASS =
  'h-12 w-full rounded-2xl border-[1.5px] border-line px-4 text-base text-navy placeholder:text-body/60'

function BrandPanel() {
  return (
    <section className="relative flex flex-1 basis-120 flex-col justify-between gap-12 overflow-hidden bg-royal px-8 py-10 md:px-14 md:py-12">
      {/* Decorative light rings. */}
      <svg
        viewBox="0 0 620 620"
        aria-hidden="true"
        className="absolute -bottom-40 -right-44 w-155"
      >
        <g fill="none" stroke="#fff" strokeOpacity="0.12">
          {[110, 170, 230, 290].map((radius) => (
            <circle key={radius} cx="310" cy="310" r={radius} />
          ))}
        </g>
      </svg>
      <Link to="/" className="relative flex items-center gap-3" aria-label="HireLucent home">
        <span className="flex size-10 items-center justify-center rounded-xl bg-white">
          <img src="/favicon.svg" alt="" className="size-7" />
        </span>
        <span className="font-display text-2xl font-extrabold tracking-tight text-white">
          HireLucent
        </span>
      </Link>
      <div className="relative flex max-w-lg flex-col gap-7">
        <p className="font-display text-3xl font-extrabold leading-tight tracking-tight text-white md:text-[44px]">
          Hire with clarity. Decide with evidence.
        </p>
        <ul className="flex flex-col gap-4 text-[17px] leading-normal text-[#d5e2ff]">
          {TRUST_POINTS.map((point) => (
            <li key={point} className="flex items-start gap-3">
              <CircleCheck className="mt-0.5 size-5 shrink-0 text-[#a9c8ff]" aria-hidden="true" />
              {point}
            </li>
          ))}
        </ul>
      </div>
      <p className="relative text-sm text-[#b9ccfa]">AI assists. People decide.</p>
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
          className="flex w-full max-w-md flex-col gap-5 rounded-[26px] border border-line bg-white p-8 shadow-card md:p-10"
        >
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-semibold uppercase tracking-widest text-brand">
              Interviewer access
            </span>
            <h1 className="text-3xl font-extrabold tracking-tight">Sign in to your workspace</h1>
          </div>

          {errorMessage && (
            <p
              role="alert"
              className="flex items-center gap-2.5 rounded-2xl bg-danger-soft px-4 py-3.5 text-[15px] font-semibold text-danger"
            >
              <CircleAlert className="size-5 shrink-0" aria-hidden="true" />
              {errorMessage}
            </p>
          )}

          <label className="flex flex-col gap-1.5 text-sm font-semibold text-navy">
            Email
            <input
              type="email"
              required
              autoComplete="username"
              placeholder="you@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={`${INPUT_CLASS} font-normal`}
            />
          </label>

          <label className="flex flex-col gap-1.5 text-sm font-semibold text-navy">
            Password
            <span className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                required
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className={`${INPUT_CLASS} pr-20 font-normal`}
              />
              <button
                type="button"
                aria-pressed={showPassword}
                onClick={() => setShowPassword((shown) => !shown)}
                className="absolute right-1.5 top-1 h-10 rounded-xl px-3.5 text-sm font-semibold text-brand hover:bg-tint"
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </span>
          </label>

          <Button type="submit" disabled={isSubmitting} className="min-h-13">
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </Button>

          <p className="border-t border-line pt-4 text-sm leading-relaxed">
            Joining as a candidate? You do not need an account. Use the private link in your
            interview invitation.
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand hover:text-brand-dark"
          >
            <ArrowLeft className="size-4" aria-hidden="true" /> Back to home
          </Link>
        </form>
      </main>
    </div>
  )
}