import {
  ArrowLeftRight,
  Check,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  FileCheck2,
  LoaderCircle,
  Minus,
  RotateCcw,
  TriangleAlert,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { useAuth } from '../../auth/AuthContext.js'
import { CLAIM_ORDER, CLAIM_RESULTS, CLAIM_SECTIONS, reviewClaim } from '../../lib/assessment.js'
import { clock, formatShortDate } from '../../lib/interviews.js'
import { fromStart } from '../../lib/room.js'
import Button from '../Button.jsx'

// Consistent claims shown before "Show N more consistent".
const FIRST_CONSISTENT = 2

const RESULT_ICONS = {
  contradiction: ArrowLeftRight,
  unverified: CircleAlert,
  not_discussed: Minus,
  consistent: Check,
  not_checked: Minus,
}

function ResultChip({ result }) {
  const chip = CLAIM_RESULTS[result]
  const Icon = RESULT_ICONS[result]
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-bold ${chip.className}`}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {chip.label}
    </span>
  )
}

function SectionTag({ section }) {
  return (
    <span className="rounded-full border border-line bg-mist px-2.5 py-0.5 text-xs font-semibold text-[#44526B]">
      {CLAIM_SECTIONS[section]}
    </span>
  )
}

function FilterChip({ isActive, onClick, children }) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onClick}
      className={`inline-flex min-h-9 items-center rounded-full px-3.5 text-[13.5px] font-semibold ${
        isActive ? 'bg-navy text-white' : 'border border-line bg-white text-navy hover:bg-tint'
      }`}
    >
      {children}
    </button>
  )
}

function Box({ label, isEmpty = false, children }) {
  return (
    <div
      className={`flex min-w-0 flex-[1_1_300px] flex-col gap-1.5 rounded-2xl px-4 py-3.5 ${
        isEmpty
          ? 'border border-dashed border-line bg-white'
          : 'border border-[#EEF2F9] bg-[#F8FAFE]'
      }`}
    >
      <span className="text-xs font-bold uppercase tracking-wider text-[#6B7890]">{label}</span>
      {children}
    </div>
  )
}

// "22 Oct, 11:20 AM"
function markedOn(at) {
  return `${formatShortDate(at)}, ${clock(at)}`
}

// Checked or dismissed, with the note: how the interviewer handled it.
function ReviewLine({ review, userId, isBusy, onUndo }) {
  const who = review.by_id != null && review.by_id === userId ? 'you' : review.by_name
  const isChecked = review.status === 'checked'
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex min-w-0 flex-col gap-1.5">
        <span
          className={`inline-flex items-center gap-1.5 self-start rounded-full px-3 py-1 text-[13px] font-bold ${
            isChecked ? 'bg-success-soft text-success' : 'bg-[#EEF1F6] text-[#44526B]'
          }`}
        >
          {isChecked && <Check className="size-3.5" aria-hidden="true" />}
          {isChecked ? 'Checked' : 'Dismissed'}
          {who ? ` by ${who}` : ''} · {markedOn(review.at)}
        </span>
        {review.note && <span className="text-sm text-navy">“{review.note}”</span>}
      </div>
      <button
        type="button"
        disabled={isBusy}
        onClick={onUndo}
        className="min-h-11 px-3.5 text-sm font-semibold text-brand hover:text-brand-dark disabled:text-body"
      >
        Undo
      </button>
    </div>
  )
}

// The note box behind Mark as checked and Dismiss.
function NoteForm({ claimId, action, isBusy, onSave, onCancel }) {
  const [note, setNote] = useState('')
  const fieldId = `claim-note-${claimId}`
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <label htmlFor={fieldId} className="text-sm font-semibold text-navy">
          Note <span className="font-normal text-body">(optional)</span>
        </label>
        <textarea
          id={fieldId}
          rows={3}
          maxLength={500}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          className="w-full resize-none rounded-xl border-[1.5px] border-line px-3.5 py-3 text-[14.5px] leading-relaxed text-navy outline-none focus:border-brand"
        />
        <span className="text-[12.5px]">Only interviewers see this note.</span>
      </div>
      <div className="flex justify-end gap-2.5">
        <Button variant="soft" disabled={isBusy} onClick={onCancel}>
          Cancel
        </Button>
        <Button disabled={isBusy} onClick={() => onSave(note)}>
          {action === 'checked' && <Check className="size-4" aria-hidden="true" />}
          {isBusy ? 'Saving…' : action === 'checked' ? 'Save as checked' : 'Save as dismissed'}
        </Button>
      </div>
    </div>
  )
}

function ClaimCard({ sessionId, claim, userId, onChanged }) {
  const [form, setForm] = useState(null)
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState('')
  const canMark = claim.result === 'contradiction' || claim.result === 'unverified'

  async function mark(action, note = '') {
    setIsBusy(true)
    setError('')
    try {
      onChanged(await reviewClaim(sessionId, claim.id, action, note))
      setForm(null)
    } catch (markError) {
      setError(markError.message)
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <article
      aria-label={`${claim.id} ${claim.title}`}
      className="flex flex-col gap-3.5 border-b border-[#EEF2F9] px-5.5 py-5 last:border-b-0"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="font-bold text-[#6B7890]">{claim.id}</span>
          <span className="text-[15.5px] font-semibold text-navy">{claim.title}</span>
          <SectionTag section={claim.section} />
        </div>
        <ResultChip result={claim.result} />
      </div>

      <div className="flex flex-wrap gap-3">
        <Box label="In the CV">
          <span className="text-[14.5px] leading-normal text-navy">“{claim.cv_text}”</span>
          {claim.detail && <span className="text-[13px]">{claim.detail}</span>}
        </Box>
        <Box label="In the interview">
          {claim.question && (
            <span className="text-[13.5px] leading-normal">
              <strong className="font-bold text-[#44526B]">Asked:</strong> “{claim.question}”
            </span>
          )}
          {claim.quote && (
            <span className="text-[14.5px] leading-normal text-navy">“{claim.quote}”</span>
          )}
          {claim.reason && <span className="text-[13px]">{claim.reason}</span>}
          {claim.turn_id != null && (
            <Link
              to={`/app/interviews/${sessionId}/transcript?turn=${claim.turn_id}`}
              className="self-start text-[13px] font-semibold text-brand hover:text-brand-dark"
            >
              {fromStart(claim.start_ms)} · Open in transcript →
            </Link>
          )}
        </Box>
      </div>

      {canMark &&
        (claim.review ? (
          <ReviewLine
            review={claim.review}
            userId={userId}
            isBusy={isBusy}
            onUndo={() => mark('reopen')}
          />
        ) : form ? (
          <NoteForm
            claimId={claim.id}
            action={form}
            isBusy={isBusy}
            onSave={(note) => mark(form, note)}
            onCancel={() => setForm(null)}
          />
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-[13.5px]">Not looked at yet</span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setForm('dismissed')}
                className="min-h-11 px-3.5 text-sm font-semibold text-body hover:text-navy"
              >
                Dismiss
              </button>
              <Button variant="outline" onClick={() => setForm('checked')}>
                <Check className="size-4" aria-hidden="true" />
                Mark as checked
              </Button>
            </div>
          </div>
        ))}
      {error && (
        <p role="alert" className="text-sm font-semibold text-danger">
          {error}
        </p>
      )}
    </article>
  )
}

// Claims shown as chips in one closed section: not discussed (nobody asked
// about them) or not checked. A chip shows its CV line.
function ChipSection({ title, note, claims, isOpen, onToggle }) {
  const [pickedId, setPickedId] = useState(null)
  const picked = claims.find((claim) => claim.id === pickedId)
  const Chevron = isOpen ? ChevronUp : ChevronDown
  return (
    <div className="border-t border-line bg-[#FBFCFF]">
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={onToggle}
        className="flex min-h-14 w-full items-center justify-between gap-3 px-5.5 text-left"
      >
        <span className="flex flex-wrap items-center gap-2.5">
          <span className="text-[15px] font-bold text-navy">{title}</span>
          <span className="rounded-full bg-[#EEF1F6] px-2.5 py-0.5 text-[12.5px] font-bold text-[#44526B]">
            {claims.length}
          </span>
          <span className="text-[13.5px]">{note}</span>
        </span>
        <Chevron className="size-4.5 shrink-0 text-body" aria-hidden="true" />
      </button>
      {isOpen && (
        <div className="flex flex-col gap-3 px-5.5 pb-5">
          <div role="group" aria-label={title} className="flex flex-wrap gap-2">
            {claims.map((claim) => (
              <button
                key={claim.id}
                type="button"
                aria-pressed={claim.id === pickedId}
                onClick={() => setPickedId(claim.id === pickedId ? null : claim.id)}
                className={`min-h-9 rounded-full px-3 text-[13.5px] font-semibold ${
                  claim.id === pickedId
                    ? 'border-[1.5px] border-brand bg-tint text-brand-dark'
                    : 'border border-line bg-white text-navy hover:bg-tint'
                }`}
              >
                {claim.title}
              </button>
            ))}
          </div>
          {picked && (
            <div className="flex flex-col gap-1 rounded-2xl border border-line bg-white px-4 py-3">
              <span className="flex items-center gap-2">
                <span className="font-bold text-[#6B7890]">{picked.id}</span>
                <SectionTag section={picked.section} />
              </span>
              <span className="text-[14.5px] leading-normal text-navy">“{picked.cv_text}”</span>
              {picked.detail && <span className="text-[13px]">{picked.detail}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ClaimsList({ sessionId, checks, onChanged }) {
  const { user } = useAuth()
  const [filter, setFilter] = useState('all')
  const [showAllConsistent, setShowAllConsistent] = useState(false)
  const [openSection, setOpenSection] = useState(null)
  const claims = checks.claims
  const byResult = (result) => claims.filter((claim) => claim.result === result)
  const counts = Object.fromEntries(
    [...CLAIM_ORDER, 'not_checked'].map((result) => [result, byResult(result).length]),
  )

  // Open marks first, then the rest, each result in CV order.
  const cardResults = filter === 'all' ? ['contradiction', 'unverified', 'consistent'] : [filter]
  let cards = cardResults
    .filter((result) => result !== 'not_discussed')
    .flatMap((result) => byResult(result).sort((a, b) => Boolean(a.review) - Boolean(b.review)))
  const consistent = cards.filter((claim) => claim.result === 'consistent')
  const hiddenConsistent =
    filter === 'all' && !showAllConsistent ? Math.max(consistent.length - FIRST_CONSISTENT, 0) : 0
  if (hiddenConsistent) {
    const shown = new Set(consistent.slice(0, FIRST_CONSISTENT).map((claim) => claim.id))
    cards = cards.filter((claim) => claim.result !== 'consistent' || shown.has(claim.id))
  }
  const showNotDiscussed = (filter === 'all' || filter === 'not_discussed') && counts.not_discussed
  const showNotChecked = filter === 'all' && counts.not_checked

  function pick(next) {
    setFilter(next)
    if (next === 'not_discussed') setOpenSection('not_discussed')
  }

  if (claims.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-line bg-white px-5 py-6 text-sm">
        The CV gave no skills, jobs, projects, certifications or education to compare.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <section
        aria-label="CV claims"
        className="overflow-hidden rounded-[20px] border border-line bg-white shadow-card"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
          <div role="group" aria-label="Show claims" className="flex flex-wrap gap-2">
            <FilterChip isActive={filter === 'all'} onClick={() => pick('all')}>
              All {claims.length}
            </FilterChip>
            {CLAIM_ORDER.filter((result) => counts[result]).map((result) => (
              <FilterChip key={result} isActive={filter === result} onClick={() => pick(result)}>
                {CLAIM_RESULTS[result].label} {counts[result]}
              </FilterChip>
            ))}
          </div>
          <span className="max-w-[440px] text-[13.5px] leading-snug">
            Points to check before deciding, not findings about the candidate. They never change the
            scores, the report or the decision.
          </span>
        </div>

        {cards.map((claim) => (
          <ClaimCard
            key={claim.id}
            sessionId={sessionId}
            claim={claim}
            userId={user?.id}
            onChanged={onChanged}
          />
        ))}
        {hiddenConsistent > 0 && (
          <div className="px-5.5 py-2.5">
            <button
              type="button"
              onClick={() => setShowAllConsistent(true)}
              className="inline-flex min-h-11 items-center gap-2 px-1.5 text-[14.5px] font-semibold text-brand hover:text-brand-dark"
            >
              <ChevronDown className="size-4" aria-hidden="true" />
              Show {hiddenConsistent} more consistent
            </button>
          </div>
        )}
        {cards.length === 0 && !showNotDiscussed && (
          <p className="px-5.5 py-6 text-sm">No claim has this result.</p>
        )}

        {showNotDiscussed ? (
          <ChipSection
            title="Not discussed in the interview"
            note="CV claims nobody asked about"
            claims={byResult('not_discussed')}
            isOpen={openSection === 'not_discussed'}
            onToggle={() =>
              setOpenSection((open) => (open === 'not_discussed' ? null : 'not_discussed'))
            }
          />
        ) : null}
        {showNotChecked ? (
          <ChipSection
            title="Could not be checked"
            note="no result could be proven from the transcript"
            claims={byResult('not_checked')}
            isOpen={openSection === 'not_checked'}
            onToggle={() =>
              setOpenSection((open) => (open === 'not_checked' ? null : 'not_checked'))
            }
          />
        ) : null}
      </section>

      <p className="text-[13px]">
        {claims.length} claims taken from the CV · checked with the evaluation on{' '}
        {markedOn(checks.checked_at)}
      </p>
    </div>
  )
}

// While only the CV claims are being checked.
function CheckingCard() {
  return (
    <section
      role="status"
      className="flex max-w-xl flex-col gap-3.5 rounded-[20px] border border-line bg-white p-5.5"
    >
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-tint text-brand">
          <LoaderCircle
            className="size-5 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
        </span>
        <div>
          <h2 className="text-[17px] font-extrabold text-navy">Checking CV claims</h2>
          <p className="text-[13.5px]">Comparing the CV's claims with the interview</p>
        </div>
      </div>
      <p className="text-[13.5px]">You can leave this page; the results appear here when ready.</p>
    </section>
  )
}

// The CV claims tab (F8): each claim in the CV compared with what was said
// in the interview, as points to check before deciding. An interview
// evaluated before the claim check, or whose claims the AI could not check,
// offers a run of the claim check alone; the report is not touched.
export default function ClaimsTab({ assessment, state, isBusy, onCheck, onChanged }) {
  const checks = assessment.claim_checks
  const busyTitle = isBusy ? 'Another evaluation is running. Wait for it to finish.' : undefined
  const failure =
    state.state === 'claims_failed' ? (
      <p role="alert" className="text-sm font-semibold text-danger">
        {state.reason}
      </p>
    ) : null

  if (state.state === 'checking_claims') return <CheckingCard />

  if (!checks) {
    return (
      <section className="flex max-w-xl flex-col items-center gap-3.5 self-center rounded-[22px] border border-line bg-white px-7 py-9 text-center shadow-card">
        <span className="flex size-13 items-center justify-center rounded-2xl bg-tint text-brand">
          <FileCheck2 className="size-6" aria-hidden="true" />
        </span>
        <h2 className="text-lg font-extrabold text-navy">CV claims not checked yet</h2>
        <p className="text-sm leading-relaxed">
          This interview was evaluated before CV claim checks were added. Checking compares the CV
          with the transcript. The report, its approval and the decision stay as they are.
        </p>
        <Button disabled={isBusy} title={busyTitle} onClick={onCheck}>
          <Check className="size-4.5" aria-hidden="true" />
          Check CV claims
        </Button>
        {failure}
      </section>
    )
  }

  if (checks.status === 'not_checked') {
    return (
      <section className="flex max-w-xl flex-col gap-3.5 rounded-[22px] border border-line bg-white p-6 shadow-card">
        <div className="flex gap-3 rounded-2xl border border-[#F3D9A8] bg-[#FFFBF3] px-4 py-3.5 text-[#6B3A00]">
          <TriangleAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <h2 className="text-base font-extrabold">CV claims not checked</h2>
            <p className="text-sm leading-relaxed">
              The AI service was not available while the claims were checked. The report is not
              affected.
            </p>
          </div>
        </div>
        {failure}
        <div className="flex justify-end">
          <Button variant="outline" disabled={isBusy} title={busyTitle} onClick={onCheck}>
            <RotateCcw className="size-4" aria-hidden="true" />
            Check again
          </Button>
        </div>
      </section>
    )
  }

  return <ClaimsList sessionId={assessment.session_id} checks={checks} onChanged={onChanged} />
}
