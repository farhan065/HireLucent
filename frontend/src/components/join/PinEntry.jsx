import { KeyRound, Lock } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { clock, longDay } from '../../lib/interviews.js'
import { checkPin } from '../../lib/join.js'
import Button from '../Button.jsx'
import CandidateLayout from './CandidateLayout.jsx'

const DIGITS = 8
const EMPTY = Array(DIGITS).fill('')

// Eight boxes, 4 + 4. Typing moves on, Backspace moves back, and a pasted
// PIN fills every box.
function PinBoxes({ digits, isError, isDisabled, onChange }) {
  const boxes = useRef([])

  function setAt(index, value) {
    const next = [...digits]
    next[index] = value
    onChange(next)
  }

  function handleInput(index, event) {
    const typed = event.target.value.replace(/\D/g, '')
    if (typed.length > 1) {
      handlePaste(typed)
      return
    }
    setAt(index, typed)
    if (typed && index < DIGITS - 1) boxes.current[index + 1]?.focus()
  }

  function handleKey(index, event) {
    if (event.key === 'Backspace' && !digits[index] && index > 0) {
      setAt(index - 1, '')
      boxes.current[index - 1]?.focus()
    }
  }

  function handlePaste(text) {
    const pasted = text.replace(/\D/g, '').slice(0, DIGITS).split('')
    onChange([...pasted, ...EMPTY].slice(0, DIGITS))
    boxes.current[Math.min(pasted.length, DIGITS - 1)]?.focus()
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {digits.map((digit, index) => (
        <span key={index} className="flex items-center gap-2">
          {index === 4 && <span aria-hidden="true" className="h-[3px] w-3.5 rounded-sm bg-line" />}
          <input
            ref={(element) => {
              boxes.current[index] = element
            }}
            id={`pin-${index}`}
            aria-label={`PIN digit ${index + 1}`}
            inputMode="numeric"
            autoComplete={index === 0 ? 'one-time-code' : 'off'}
            maxLength={DIGITS}
            value={digit}
            disabled={isDisabled}
            onChange={(event) => handleInput(index, event)}
            onKeyDown={(event) => handleKey(index, event)}
            onPaste={(event) => {
              event.preventDefault()
              handlePaste(event.clipboardData.getData('text'))
            }}
            className={`h-15 w-12.5 rounded-[14px] border-[1.5px] text-center font-display text-[26px] font-extrabold text-navy focus:outline-none disabled:bg-[#f7f9fc] ${
              isError ? 'border-danger' : digit ? 'border-brand' : 'border-line focus:border-brand'
            }`}
          />
        </span>
      ))}
    </div>
  )
}

// The first step of an interview link with a PIN: the 8-digit PIN from the
// calendar invitation. Wrong tries are counted on the server; the fifth
// locks the link for 15 minutes.
export default function PinEntry({ token, link, onAccepted, onEnded }) {
  const [digits, setDigits] = useState(EMPTY)
  const [isChecking, setIsChecking] = useState(false)
  const [error, setError] = useState('')
  const [lockedUntil, setLockedUntil] = useState(null)
  const pin = digits.join('')
  const isLocked = Boolean(lockedUntil)

  // The lock ends on the clock, so the boxes open again by themselves.
  useEffect(() => {
    if (!lockedUntil) return undefined
    const wait = Math.max(0, new Date(lockedUntil) - Date.now())
    const timer = setTimeout(() => setLockedUntil(null), wait + 500)
    return () => clearTimeout(timer)
  }, [lockedUntil])

  async function handleSubmit(event) {
    event.preventDefault()
    if (pin.length !== DIGITS || isChecking || isLocked) return
    setIsChecking(true)
    setError('')
    try {
      const answer = await checkPin(token, pin)
      if (answer.result === 'ok') {
        onAccepted(pin)
        return
      }
      setDigits(EMPTY)
      if (answer.result === 'locked') setLockedUntil(answer.locked_until)
      else {
        const tries = answer.tries_left === 1 ? '1 try' : `${answer.tries_left} tries`
        setError(`That PIN is not right. Check the invitation and try again. ${tries} left.`)
      }
    } catch (checkError) {
      if (checkError.status === 404) onEnded()
      else setError(checkError.message)
    } finally {
      setIsChecking(false)
    }
  }

  return (
    <CandidateLayout note="Interview invitation">
      <div className="mx-auto flex w-full max-w-140 flex-col gap-6">
        <span className="text-[15px] font-semibold text-brand">
          {link.job_title} · {longDay(link.scheduled_start)}, {clock(link.scheduled_start)}
        </span>
        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4.5 rounded-card border border-line bg-white p-6.5 shadow-card"
        >
          <span className="flex size-13 items-center justify-center rounded-2xl bg-tint text-brand">
            <KeyRound className="size-6" aria-hidden="true" />
          </span>
          <div className="flex flex-col gap-2">
            <h1 className="text-[28px] font-extrabold tracking-tight text-balance">
              Enter your interview PIN
            </h1>
            <p className="text-base leading-relaxed">
              Your 8-digit PIN is in your calendar invitation, right under the join link. It keeps
              your interview private, even if someone else sees the link.
            </p>
          </div>
          <div className="flex flex-col gap-2.5">
            <label htmlFor="pin-0" className="text-sm font-semibold text-navy">
              Interview PIN
            </label>
            <PinBoxes
              digits={digits}
              isError={Boolean(error)}
              isDisabled={isLocked || isChecking}
              onChange={(next) => {
                setDigits(next)
                setError('')
              }}
            />
          </div>
          {error && (
            <p role="alert" className="text-sm font-semibold text-danger">
              {error}
            </p>
          )}
          {isLocked && (
            <p
              role="alert"
              className="flex items-start gap-2.5 rounded-2xl bg-amber-soft px-3.5 py-3 text-sm leading-normal text-amber"
            >
              <Lock className="mt-px size-4.5 shrink-0" aria-hidden="true" />
              <span>
                Too many wrong tries. For your safety the link is locked until{' '}
                <strong>{clock(lockedUntil)}</strong>. Then you can try again.
              </span>
            </p>
          )}
          <Button
            type="submit"
            className="min-h-12 self-stretch"
            disabled={pin.length !== DIGITS || isChecking || isLocked}
          >
            {isChecking ? 'Checking…' : 'Continue'}
          </Button>
          {pin.length !== DIGITS && !isLocked && (
            <p className="-mt-1.5 text-center text-[13.5px]">Enter all 8 digits to continue.</p>
          )}
          <div className="flex flex-col gap-1.5 border-t border-line/60 pt-4 text-sm">
            <span className="font-semibold text-navy">Can’t find your PIN?</span>
            <span>
              Open the invitation from HireLucent Careers in your calendar or email. If it is
              missing, reply to the invitation and the hiring team will send a new one.
            </span>
          </div>
        </form>
      </div>
    </CandidateLayout>
  )
}
