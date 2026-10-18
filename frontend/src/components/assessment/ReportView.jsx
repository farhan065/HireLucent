import { CircleAlert, CircleCheck, Download, LoaderCircle, PenLine, Printer } from 'lucide-react'
import { useState } from 'react'
import {
  MAX_NOTE_CHARS,
  MAX_SUMMARY_CHARS,
  SUITABILITY,
  oneDecimal,
  printFile,
  readReportPdf,
  reviewReport,
  saveFile,
  scoreParts,
} from '../../lib/assessment.js'
import { clock, shortDay } from '../../lib/interviews.js'
import Button from '../Button.jsx'
import ConfirmDialog from '../ConfirmDialog.jsx'
import SourceChip from './SourceChip.jsx'

const CARD = 'rounded-[20px] border border-line bg-white'
const HEADING = 'font-display text-lg font-extrabold text-navy'
const FIELD =
  'w-full rounded-2xl border-[1.5px] border-line bg-white px-3.5 py-3 text-[15px] leading-relaxed text-navy focus:border-brand focus:shadow-[0_0_0_3px_#E8F0FF] focus:outline-none'

function when(value) {
  return `${shortDay(value)}, ${clock(value)}`
}

function Claim({ claim, sessionId }) {
  return (
    <div className="flex flex-col gap-1.5 border-b border-[#EEF2F9] pb-3.5 last:border-b-0 last:pb-0">
      <span className="text-[15px] text-navy">{claim.text}</span>
      {claim.sources.length > 0 && (
        <span className="flex flex-wrap gap-1.5">
          {claim.sources.map((source, index) => (
            <SourceChip key={index} sessionId={sessionId} source={source} />
          ))}
        </span>
      )}
    </div>
  )
}

function ClaimSection({ title, dot, claims, sessionId, empty }) {
  return (
    <section className={`${CARD} flex flex-col gap-3.5 px-6 py-5.5`}>
      <h2 className={`${HEADING} flex items-center gap-2.5`}>
        <span aria-hidden="true" className={`size-2.5 rounded-full ${dot}`} />
        {title}
        <span className="font-sans text-[13px] font-semibold text-[#6B7890]">{claims.length}</span>
      </h2>
      {claims.length === 0 ? (
        <p className="text-sm">{empty}</p>
      ) : (
        claims.map((claim) => <Claim key={claim.id} claim={claim} sessionId={sessionId} />)
      )}
    </section>
  )
}

function Findings({ title, note, claims, sessionId, tone }) {
  return (
    <section
      className={`flex flex-col gap-3 rounded-[20px] border px-5.5 py-5 ${
        tone === 'amber' ? 'border-[#F3D9A8] bg-[#FFFBF3]' : 'border-line bg-white'
      }`}
    >
      <h2 className="font-display text-[17px] font-extrabold text-navy">
        {title}{' '}
        <span className="font-sans text-[13px] font-semibold text-[#6B7890]">{claims.length}</span>
      </h2>
      <p className={`text-[13px] ${tone === 'amber' ? 'text-amber' : ''}`}>{note}</p>
      {claims.length === 0 ? (
        <p className="text-sm">None.</p>
      ) : (
        claims.map((claim) => <Claim key={claim.id} claim={claim} sessionId={sessionId} />)
      )}
    </section>
  )
}

function ScoreSum({ assessment }) {
  const label = SUITABILITY[assessment.suitability]
  if (assessment.overall_score == null) {
    return (
      <section className={`${CARD} flex flex-col gap-2 px-5 py-4.5 text-sm leading-relaxed`}>
        <h2 className="font-display text-base font-extrabold text-navy">How the score is made</h2>
        <p>
          No overall score:{' '}
          {assessment.interview_score == null
            ? 'the interview had no job-related questions.'
            : 'the candidate has no CV score.'}
        </p>
      </section>
    )
  }
  const parts = scoreParts(assessment)
  return (
    <section className={`${CARD} flex flex-col gap-2.5 px-5 py-4.5`}>
      <h2 className="mb-1 font-display text-base font-extrabold text-navy">
        How the score is made
      </h2>
      <div className="flex justify-between gap-3 text-sm">
        <span>
          CV score <span className="text-[12.5px]">(screening)</span>
        </span>
        <span className="whitespace-nowrap tabular-nums text-navy">
          {oneDecimal(assessment.cv_score)} × 40% = <strong>{parts.cv}</strong>
        </span>
      </div>
      <div className="flex justify-between gap-3 text-sm">
        <span>Interview</span>
        <span className="whitespace-nowrap tabular-nums text-navy">
          {oneDecimal(assessment.interview_score)} × 60% = <strong>{parts.interview}</strong>
        </span>
      </div>
      <div className="flex justify-between gap-3 border-t border-line pt-2 text-[14.5px] font-bold text-navy">
        <span>Overall</span>
        <span className="whitespace-nowrap tabular-nums">
          {oneDecimal(assessment.overall_score)} · {label?.label}
        </span>
      </div>
      <p className="text-[12.5px] leading-snug">
        Strong fit 70+, Possible fit 60–69, Not a fit below 60. Decision support only: the decision
        stays with you.
      </p>
    </section>
  )
}

function ReviewKey() {
  return (
    <section className={`${CARD} flex flex-col gap-2.5 px-5 py-4.5 text-[13.5px] leading-normal`}>
      <h2 className="font-display text-base font-extrabold text-navy">Your review</h2>
      <p>
        <strong className="text-navy">Approve report</strong>: the report becomes final and the
        candidate is marked assessed.
      </p>
      <p>
        <strong className="text-navy">Edit</strong>: change the summary in your own words, or remove
        a point. Points cannot be added.
      </p>
      <p>
        <strong className="text-navy">Request changes</strong>: write a note and the AI rewrites the
        report, checking every point again.
      </p>
    </section>
  )
}

// The interviewer's own changes: a new summary and points removed. Nothing
// can be added, because a typed point would have no evidence.
function EditForm({ assessment, isSaving, onCancel, onSave }) {
  const [summary, setSummary] = useState(assessment.report ?? '')
  const [removed, setRemoved] = useState(() => new Set())
  const summaryChanged = summary.trim() !== (assessment.report ?? '').trim()
  const canSave = summary.trim() !== '' && (summaryChanged || removed.size > 0)

  function toggle(id) {
    setRemoved((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function points(title, claims) {
    if (!claims?.length) return null
    return (
      <div className="flex flex-col gap-2">
        <span className="text-[15px] font-bold text-navy">{title}</span>
        {claims.map((claim) => {
          const isRemoved = removed.has(claim.id)
          return (
            <div
              key={claim.id}
              className={`flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 ${
                isRemoved
                  ? 'border border-dashed border-[#F3C4C0] bg-[#FDF3F2]'
                  : 'border border-[#EEF2F9]'
              }`}
            >
              <span
                className={`text-sm ${isRemoved ? 'text-[#9AA6BA] line-through' : 'text-navy'}`}
              >
                {claim.text}
              </span>
              <button
                type="button"
                onClick={() => toggle(claim.id)}
                className={`min-h-8.5 shrink-0 rounded-full px-3 text-[13px] font-semibold ${
                  isRemoved
                    ? 'text-brand hover:text-brand-dark'
                    : 'border border-[#F3C4C0] bg-white text-danger hover:bg-danger-soft'
                }`}
              >
                {isRemoved ? 'Undo' : 'Remove'}
              </button>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <section className={`${CARD} flex flex-col gap-4 border-[1.5px] border-[#A9C8FF] px-6 py-5.5`}>
      <div className="flex flex-col gap-2">
        <label htmlFor="report-summary" className="text-[15px] font-bold text-navy">
          Summary
        </label>
        <textarea
          id="report-summary"
          rows={4}
          maxLength={MAX_SUMMARY_CHARS}
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          className={FIELD}
        />
        <span className="text-right text-[12.5px] tabular-nums">
          {summary.length} / {MAX_SUMMARY_CHARS}
        </span>
      </div>
      {points('Strengths', assessment.strengths)}
      {points('Weaknesses', assessment.weaknesses)}
      <p className="text-[13px] leading-normal">
        Points cannot be added here, because a typed point would have no evidence. To add one, use
        Request changes. Gaps and areas to verify are worked out from the interview and stay as they
        are.
      </p>
      <div className="flex justify-end gap-2.5">
        <Button variant="soft" disabled={isSaving} onClick={onCancel}>
          Cancel
        </Button>
        <Button
          disabled={!canSave || isSaving}
          onClick={() =>
            onSave({
              action: 'edit',
              summary: summaryChanged ? summary.trim() : null,
              remove: [...removed],
            })
          }
        >
          {isSaving ? 'Saving…' : 'Save changes'}
        </Button>
      </div>
      <span className="text-[12.5px]">
        Saved changes keep the report a draft, so it can still be checked before approving.
      </span>
    </section>
  )
}

// The report of one interview: summary, strengths and weaknesses with their
// sources, evidence gaps and areas to verify. A draft can be approved,
// edited or rewritten by the AI following a note.
export default function ReportView({ assessment, candidateName, fileName, onChanged }) {
  const [mode, setMode] = useState('view')
  const [dialog, setDialog] = useState(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState('')
  const isDraft = assessment.status === 'draft'
  const sessionId = assessment.session_id

  async function send(body, kind) {
    setBusy(kind)
    setError('')
    try {
      const updated = await reviewReport(sessionId, body)
      onChanged(updated)
      setMode('view')
      setNote('')
      return true
    } catch (sendError) {
      setError(sendError.message)
      return false
    } finally {
      setBusy(null)
    }
  }

  async function approve() {
    if (await send({ action: 'approve' }, 'approve')) setDialog(null)
  }

  function requestChanges() {
    setDialog(null)
    send({ action: 'request_changes', note: note.trim() }, 'rewrite')
  }

  const isRewriting = busy === 'rewrite'

  // The same PDF is printed or saved, so both always match.
  async function exportPdf(kind) {
    setBusy(kind)
    setError('')
    try {
      const file = await readReportPdf(sessionId)
      if (kind === 'print') printFile(file)
      else saveFile(file, fileName)
    } catch (exportError) {
      setError(exportError.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-end gap-2.5">
        <button
          type="button"
          disabled={busy !== null || mode === 'edit'}
          onClick={() => exportPdf('print')}
          className="inline-flex min-h-10 items-center gap-2 rounded-full border border-line bg-white px-4 text-sm font-semibold text-navy hover:bg-tint disabled:cursor-not-allowed disabled:text-[#A8B3C6]"
        >
          <Printer className="size-4.5" aria-hidden="true" />
          {busy === 'print' ? 'Preparing…' : 'Print'}
        </button>
        <Button
          variant="outline"
          className="min-h-10 px-4.5 text-sm"
          disabled={busy !== null || mode === 'edit'}
          onClick={() => exportPdf('pdf')}
        >
          <Download className="size-4.5" aria-hidden="true" />
          {busy === 'pdf' ? 'Preparing…' : 'Download PDF'}
        </Button>
      </div>
      {isDraft && mode === 'view' && !isRewriting && (
        <section
          role="status"
          className="flex flex-wrap items-center justify-between gap-4 rounded-[18px] border border-[#F3D9A8] bg-[#FFFBF3] px-5 py-3.5"
        >
          <div className="flex items-start gap-3">
            <PenLine className="mt-0.5 size-5 shrink-0 text-amber" aria-hidden="true" />
            <div>
              <p className="text-[15px] font-bold text-navy">Draft: waiting for your review</p>
              <p className="text-[13.5px] leading-snug">
                Written by the AI on {when(assessment.updated_at)}. Check the points and their
                sources, then approve it, edit it, or ask for changes.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => setDialog('changes')}
              className="min-h-10.5 px-4 text-[14.5px] font-semibold text-brand hover:text-brand-dark"
            >
              Request changes
            </button>
            <Button variant="outline" className="min-h-10.5" onClick={() => setMode('edit')}>
              Edit
            </Button>
            <Button className="min-h-10.5" onClick={() => setDialog('approve')}>
              Approve report
            </Button>
          </div>
        </section>
      )}

      {isRewriting && (
        <section
          role="status"
          className="flex flex-col gap-1.5 rounded-[18px] border border-[#A9C8FF] bg-white px-5 py-4"
        >
          <span className="flex items-center gap-2.5 text-[15px] font-semibold text-brand-dark">
            <LoaderCircle
              className="size-4.5 animate-spin motion-reduce:animate-none"
              aria-hidden="true"
            />
            Rewriting the report with your note…
          </span>
          <span className="text-[13px]">
            The AI checks every point again. This takes about 10–30 seconds.
          </span>
        </section>
      )}

      {assessment.status === 'approved' && (
        <p className="flex items-start gap-2.5 rounded-2xl bg-success-soft px-4 py-3 text-sm leading-snug text-[#0B5C41]">
          <CircleCheck className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          <span>
            <strong>Report approved</strong>
            {assessment.approved_by_name ? ` by ${assessment.approved_by_name}` : ''}
            {assessment.approved_at ? ` on ${when(assessment.approved_at)}` : ''}.
          </span>
        </p>
      )}

      {error && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-2xl border border-[#F3C4C0] bg-white px-4 py-3 text-sm leading-snug text-danger"
        >
          <CircleAlert className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}

      <div className="flex flex-wrap items-start gap-5.5">
        <article
          aria-label="Report"
          className={`flex min-w-0 flex-[999_1_560px] flex-col gap-4.5 ${
            isRewriting ? 'pointer-events-none opacity-50' : ''
          }`}
        >
          {mode === 'edit' ? (
            <EditForm
              assessment={assessment}
              isSaving={busy === 'edit'}
              onCancel={() => setMode('view')}
              onSave={(body) => send(body, 'edit')}
            />
          ) : (
            <>
              <section className={`${CARD} px-6 py-5.5 shadow-card`}>
                <h2 className={`${HEADING} mb-2.5`}>Summary</h2>
                <p className="text-[15.5px] leading-relaxed text-navy">{assessment.report}</p>
              </section>
              <ClaimSection
                title="Strengths"
                dot="bg-success"
                claims={assessment.strengths ?? []}
                sessionId={sessionId}
                empty="No strength could be traced to the CV or the transcript."
              />
              <ClaimSection
                title="Weaknesses"
                dot="bg-danger"
                claims={assessment.weaknesses ?? []}
                sessionId={sessionId}
                empty="No weakness was found."
              />
            </>
          )}
          <div className="grid grid-cols-1 gap-4.5 md:grid-cols-2">
            <Findings
              title="Evidence gaps"
              note="Requirements the interview never explored."
              claims={assessment.gaps ?? []}
              sessionId={sessionId}
              tone="amber"
            />
            <Findings
              title="Areas to verify"
              note="To check in a follow-up."
              claims={assessment.areas_to_verify ?? []}
              sessionId={sessionId}
            />
          </div>
          <p className="text-[13px] leading-normal">
            Every point shows where it comes from: a question chip opens the transcript at that
            moment; a CV chip shows what screening found. Points the AI could not trace were left
            out.
          </p>
        </article>

        <aside className="flex max-w-[360px] flex-[1_1_300px] flex-col gap-4">
          <ScoreSum assessment={assessment} />
          {isDraft && <ReviewKey />}
        </aside>
      </div>

      {dialog === 'approve' && (
        <ConfirmDialog
          title="Approve this report?"
          confirmLabel="Approve report"
          confirmVariant="primary"
          busyLabel="Approving…"
          isBusy={busy === 'approve'}
          onConfirm={approve}
          onCancel={() => setDialog(null)}
        >
          <p>
            The report becomes final and {candidateName} is marked assessed. To change it later,
            evaluate the interview again.
          </p>
        </ConfirmDialog>
      )}

      {dialog === 'changes' && (
        <ConfirmDialog
          title="What should the AI change?"
          confirmLabel="Rewrite report"
          confirmVariant="primary"
          isWide
          confirmDisabled={!note.trim()}
          onConfirm={requestChanges}
          onCancel={() => setDialog(null)}
        >
          <label htmlFor="change-note" className="sr-only">
            Your note
          </label>
          <textarea
            id="change-note"
            rows={4}
            autoFocus
            maxLength={MAX_NOTE_CHARS}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            className={FIELD}
          />
          <span className="text-[13px]">
            For example: “shorter summary”, “mention the leadership example”, “be more specific
            about R3”.
          </span>
          <span className="text-[13px]">
            The AI rewrites the summary, strengths and weaknesses, and checks every point against
            the transcript and CV again. Points it cannot trace are left out.
          </span>
        </ConfirmDialog>
      )}
    </div>
  )
}
