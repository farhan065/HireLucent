import { Check, Copy, LoaderCircle, Plus, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { markAsked, readQuestions, suggestQuestions } from '../../lib/room.js'
import Skeleton from '../Skeleton.jsx'

// The most questions one interview can have; the backend keeps to it too.
const MAX_QUESTIONS = 30
const COPIED_MS = 2000

const REASONS = {
  partly_met: { label: 'Partly met', className: 'bg-warning-soft text-warning' },
  not_in_cv: { label: 'Not in CV', className: 'bg-danger-soft text-danger' },
  cv_claim: { label: 'CV claim', className: 'bg-teal-soft text-teal' },
}
const CHIP = 'rounded-full px-2 py-0.5 text-xs font-semibold'
const SMALL_BUTTON = 'inline-flex min-h-7.5 items-center gap-1.5 rounded-full px-2.5 text-[12.5px] font-semibold'

function QuestionCard({ question, onToggleAsked }) {
  const [isCopied, setIsCopied] = useState(false)
  const reason = REASONS[question.reason] ?? REASONS.cv_claim

  useEffect(() => {
    if (!isCopied) return undefined
    const timer = setTimeout(() => setIsCopied(false), COPIED_MS)
    return () => clearTimeout(timer)
  }, [isCopied])

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(question.question)
      setIsCopied(true)
    } catch {
      // Copying is a convenience; the question stays visible to read out.
    }
  }

  return (
    <article
      className={`flex flex-col gap-1.75 rounded-2xl border border-[#e6e0ff] bg-white px-3.25 py-3 shadow-[inset_3px_0_0_#6e56e8] ${
        question.asked ? 'opacity-55' : ''
      }`}
    >
      <span className="flex min-w-0 flex-wrap gap-1.5">
        {question.requirement_id && (
          <span
            title={question.requirement ?? undefined}
            className={`${CHIP} max-w-full truncate bg-violet-soft text-violet`}
          >
            {question.requirement_id}
            {question.requirement && ` ${question.requirement}`}
          </span>
        )}
        <span className={`${CHIP} ${reason.className}`}>{reason.label}</span>
      </span>
      <p className="text-[13.5px] leading-snug text-navy">{question.question}</p>
      <p className="text-[12.5px] leading-snug">Why: {question.why}</p>
      <span className="flex items-center justify-between gap-1.5">
        <button
          type="button"
          onClick={handleCopy}
          className={`${SMALL_BUTTON} bg-violet-soft text-violet hover:bg-violet-soft/70`}
        >
          {isCopied ? (
            <Check className="size-3.5" aria-hidden="true" />
          ) : (
            <Copy className="size-3.5" aria-hidden="true" />
          )}
          {isCopied ? 'Copied' : 'Copy'}
        </button>
        <button
          type="button"
          aria-pressed={question.asked}
          onClick={onToggleAsked}
          title={question.asked ? 'Mark as not asked' : undefined}
          className={
            question.asked
              ? `${SMALL_BUTTON} text-success hover:bg-success-soft`
              : `${SMALL_BUTTON} border-[1.5px] border-[#d9d0ff] bg-white text-violet hover:border-violet/60`
          }
        >
          {question.asked && <Check className="size-3.5" aria-hidden="true" strokeWidth={2.6} />}
          {question.asked ? 'Asked' : 'Mark as asked'}
        </button>
      </span>
    </article>
  )
}

// Before the first questions: what they are and the Generate button.
function Empty({ firstName, isWorking, error, onGenerate }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3.5 px-6 py-8 text-center">
      <span className="flex size-16 items-center justify-center rounded-[20px] bg-violet-soft text-violet">
        <Sparkles className="size-7.5" aria-hidden="true" />
      </span>
      <h2 className="text-lg font-extrabold tracking-tight">Questions made for {firstName}</h2>
      <p className="text-sm leading-relaxed">
        Get 5 questions based on {firstName}&apos;s CV and screening results, starting with the
        areas the CV covers least.
      </p>
      <button
        type="button"
        onClick={onGenerate}
        disabled={isWorking}
        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-violet px-5.5 font-display text-[15px] font-bold text-white hover:opacity-90 disabled:opacity-70"
      >
        {isWorking && <LoaderCircle className="size-4.5 animate-spin" aria-hidden="true" />}
        {isWorking ? 'Writing questions…' : 'Generate questions'}
      </button>
      {error ? (
        <p role="alert" className="text-[13px] font-semibold text-danger">
          {error}
        </p>
      ) : (
        <span className="text-[12.5px]">Takes a few seconds. Only you see them.</span>
      )}
    </div>
  )
}

// The Suggested questions tab: questions the AI wrote from this candidate's
// CV and screening results, five at a time, saved with the interview.
export default function SuggestedQuestions({ sessionId, candidateName }) {
  const [questions, setQuestions] = useState(null)
  const [isWorking, setIsWorking] = useState(false)
  const [error, setError] = useState('')
  const listRef = useRef(null)
  const shownCount = useRef(0)
  const firstName = candidateName.split(/\s+/)[0] || candidateName

  useEffect(() => {
    let isCurrent = true
    readQuestions(sessionId)
      .then((loaded) => isCurrent && setQuestions(loaded))
      .catch((loadError) => {
        if (!isCurrent) return
        setQuestions([])
        setError(loadError.message)
      })
    return () => {
      isCurrent = false
    }
  }, [sessionId])

  // After "More questions", bring the first new one into view.
  useEffect(() => {
    if (!questions) return
    const previous = shownCount.current
    shownCount.current = questions.length
    if (previous === 0 || questions.length <= previous) return
    listRef.current?.children[previous]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [questions])

  async function handleGenerate() {
    setIsWorking(true)
    setError('')
    try {
      setQuestions(await suggestQuestions(sessionId))
    } catch (generateError) {
      setError(generateError.message)
    } finally {
      setIsWorking(false)
    }
  }

  async function handleToggle(question) {
    const asked = !question.asked
    const update = (value) =>
      setQuestions((list) =>
        list.map((item) => (item.id === question.id ? { ...item, asked: value } : item)),
      )
    update(asked)
    setError('')
    try {
      await markAsked(sessionId, question.id, asked)
    } catch (markError) {
      update(!asked)
      setError(markError.message)
    }
  }

  if (questions === null) {
    return (
      <div className="flex flex-col gap-2.5 p-4">
        <Skeleton className="h-36 w-full" />
        <Skeleton className="h-36 w-full" />
      </div>
    )
  }
  if (questions.length === 0) {
    return (
      <Empty firstName={firstName} isWorking={isWorking} error={error} onGenerate={handleGenerate} />
    )
  }

  const askedCount = questions.filter((item) => item.asked).length
  const isFull = questions.length >= MAX_QUESTIONS
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 px-4 pb-2 pt-3">
        <span className="text-[13px]">
          <strong className="font-semibold text-navy">
            {questions.length} questions for {firstName}
          </strong>{' '}
          · {askedCount} asked
        </span>
        <span className="text-xs font-semibold text-violet">From the CV</span>
      </div>
      <div
        ref={listRef}
        className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto px-4 pb-3 pt-0.5 [&>*]:shrink-0"
      >
        {questions.map((question) => (
          <QuestionCard
            key={question.id}
            question={question}
            onToggleAsked={() => handleToggle(question)}
          />
        ))}
      </div>
      <div className="flex shrink-0 flex-col gap-1.5 border-t border-line px-4 pb-3 pt-2.5">
        {!isFull && (
          <button
            type="button"
            onClick={handleGenerate}
            disabled={isWorking}
            className="flex min-h-10 items-center justify-center gap-2 rounded-full border-[1.5px] border-[#d9d0ff] bg-white font-display text-[13.5px] font-bold text-violet hover:border-violet/60 disabled:opacity-70"
          >
            {isWorking ? (
              <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Plus className="size-4" aria-hidden="true" />
            )}
            {isWorking ? 'Writing questions…' : 'More questions'}
          </button>
        )}
        {error ? (
          <p role="alert" className="text-center text-xs font-semibold text-danger">
            {error}
          </p>
        ) : (
          <span className="text-center text-xs">
            {isFull ? 'That is the most for one interview.' : '5 more, without repeating these'}
          </span>
        )}
      </div>
    </div>
  )
}
