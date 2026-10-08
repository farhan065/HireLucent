import { ChevronDown, ChevronRight, Star } from 'lucide-react'
import { useState } from 'react'
import { apiRequest } from '../../lib/api.js'
import Button from '../Button.jsx'
import ConfirmDialog from '../ConfirmDialog.jsx'
import StatusChip from '../StatusChip.jsx'
import DeleteCandidateButton from './DeleteCandidateButton.jsx'
import { MatchCounts, RankBadge } from './MatchRanking.jsx'
import {
  HEADING,
  Initials,
  LABEL,
  RowActions,
  UnrankedRow,
  ViewCvLink,
} from './candidates.jsx'
import { SHORTLISTED_CHIP } from '../../lib/jobs.js'

const ROW = 'grid grid-cols-[2.75rem_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 px-5 lg:grid-cols-[3.25rem_minmax(0,1.5fr)_minmax(9.5rem,1fr)_minmax(0,1fr)_7.5rem_15.5rem]'

// The same shares as the backend uses for the final score.
const CRITERIA_SHARE = 0.8
const ATS_SHARE = 0.2

const DIMENSIONS = [
  ['technical_skills', 'Technical skills'],
  ['experience', 'Relevant experience'],
  ['qualifications', 'Qualifications'],
]

const SCORED_CHIP = { tone: 'success', label: 'Scored' }

// 82.14 → 82.1, 74.0 → 74
function formatScore(value) {
  return Math.round(value * 10) / 10
}

function percent(share) {
  return `${Math.round(share * 100)}%`
}

function Bar({ score, color = 'bg-brand', className = '' }) {
  return (
    <div className={`h-1.5 overflow-hidden rounded-full bg-tint ${className}`}>
      <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
    </div>
  )
}

function FinalScore({ scores }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-3">
        <span className="font-display text-[19px] font-extrabold text-navy">
          {formatScore(scores.final_score)}
        </span>
        <Bar
          score={scores.final_score}
          color={scores.final_rank === 1 ? 'bg-success' : 'bg-brand'}
          className="hidden min-w-16 flex-1 sm:block"
        />
      </div>
      <p className="text-[13px]">
        Criteria {formatScore(scores.criteria_score)} · ATS {formatScore(scores.ats_score)}
      </p>
    </div>
  )
}

// Adds the candidate to the shortlist, or takes them off it.
function ShortlistButton({ candidate, onChanged }) {
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState('')
  const isShortlisted = candidate.status === 'shortlisted'

  async function handleClick() {
    setIsBusy(true)
    setError('')
    try {
      await apiRequest(`/candidates/${candidate.id}/shortlist`, {
        method: 'PUT',
        body: { shortlisted: !isShortlisted },
      })
      onChanged()
    } catch (changeError) {
      setError(changeError.message)
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <span className="flex flex-col items-end">
      <button
        type="button"
        onClick={handleClick}
        disabled={isBusy}
        className={`flex min-h-10 items-center gap-1.5 whitespace-nowrap rounded-full border-[1.5px] px-3.5 text-sm font-semibold disabled:opacity-60 ${
          isShortlisted
            ? 'border-line bg-white text-body hover:bg-mist'
            : 'border-brand/40 bg-white text-brand hover:bg-tint'
        }`}
      >
        {!isShortlisted && <Star className="size-4" aria-hidden="true" />}
        {isShortlisted ? 'Remove' : 'Shortlist'}
        <span className="sr-only"> {candidate.full_name}</span>
      </button>
      {error && (
        <span role="alert" className="text-xs text-danger">
          {error}
        </span>
      )}
    </span>
  )
}

function RuleInput({ label, value, min, max, step, isActive, onChange, onFocus }) {
  return (
    <input
      type="number"
      aria-label={label}
      value={value}
      min={min}
      max={max}
      step={step}
      onChange={(event) => onChange(event.target.value)}
      onFocus={onFocus}
      className={`h-10 w-16 rounded-xl border border-line bg-white text-center text-[15px] font-semibold text-navy ${
        isActive ? '' : 'opacity-60'
      }`}
    />
  )
}

// Shortlist by a rule: the top N of the ranking, or everyone with at least
// a final score. It only adds; nobody already shortlisted is removed.
function ShortlistBar({ jobId, rankedCount, shortlistedCount, onChanged }) {
  const [rule, setRule] = useState('top')
  const [top, setTop] = useState(String(Math.min(3, rankedCount)))
  const [minScore, setMinScore] = useState('70')
  const [isBusy, setIsBusy] = useState(false)
  const [isClearing, setIsClearing] = useState(false)
  const [error, setError] = useState('')

  const topValue = Number(top)
  const scoreValue = Number(minScore)
  const isValid =
    rule === 'top'
      ? Number.isInteger(topValue) && topValue >= 1
      : minScore !== '' && scoreValue >= 0 && scoreValue <= 100

  async function send(method, body) {
    setIsBusy(true)
    setError('')
    try {
      await apiRequest(`/jobs/${jobId}/shortlist`, { method, body })
      setIsClearing(false)
      onChanged()
    } catch (sendError) {
      setError(sendError.message)
    } finally {
      setIsBusy(false)
    }
  }

  function handleApply(event) {
    event.preventDefault()
    send('POST', rule === 'top' ? { top: topValue } : { min_score: scoreValue })
  }

  const radio = (value, text) => (
    <label className="flex min-h-10 cursor-pointer items-center gap-2 text-[15px]">
      <input
        type="radio"
        name="shortlist-rule"
        value={value}
        checked={rule === value}
        onChange={() => setRule(value)}
        className="size-4.5 accent-brand"
      />
      <span className={rule === value ? 'text-navy' : ''}>{text}</span>
    </label>
  )

  return (
    <form
      onSubmit={handleApply}
      aria-label="Shortlist by a rule"
      className="mx-5 mb-4 flex flex-wrap items-center gap-x-5 gap-y-3 rounded-2xl border border-line bg-mist px-4 py-3"
    >
      <span className="font-display text-[15px] font-bold text-navy">Shortlist</span>
      <div className="flex flex-wrap items-center gap-2.5">
        {radio('top', 'Top')}
        <RuleInput
          label="How many of the top candidates"
          value={top}
          min={1}
          max={rankedCount}
          step={1}
          isActive={rule === 'top'}
          onChange={setTop}
          onFocus={() => setRule('top')}
        />
        <span className={`text-[15px] ${rule === 'top' ? 'text-navy' : ''}`}>candidates</span>
      </div>
      <div className="flex flex-wrap items-center gap-2.5">
        {radio('score', 'Final score of at least')}
        <RuleInput
          label="Lowest final score"
          value={minScore}
          min={0}
          max={100}
          step={0.1}
          isActive={rule === 'score'}
          onChange={setMinScore}
          onFocus={() => setRule('score')}
        />
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-4">
        {shortlistedCount > 0 && (
          <button
            type="button"
            onClick={() => setIsClearing(true)}
            className="min-h-10 text-[15px] font-semibold text-brand hover:text-brand-dark"
          >
            Clear shortlist
          </button>
        )}
        <Button type="submit" disabled={isBusy || !isValid}>
          <Star className="size-4.5" aria-hidden="true" />
          {isBusy && !isClearing ? 'Applying…' : 'Apply'}
        </Button>
      </div>
      {error && !isClearing && (
        <p role="alert" className="basis-full text-sm font-semibold text-danger">
          {error}
        </p>
      )}

      {isClearing && (
        <ConfirmDialog
          title="Clear the shortlist?"
          confirmLabel="Clear shortlist"
          busyLabel="Clearing…"
          confirmVariant="primary"
          isBusy={isBusy}
          error={error}
          onConfirm={() => send('DELETE')}
          onCancel={() => setIsClearing(false)}
        >
          <p>
            {shortlistedCount} {shortlistedCount === 1 ? 'candidate is' : 'candidates are'} taken
            off the shortlist. Their scores and ranks do not change.
          </p>
        </ConfirmDialog>
      )}
    </form>
  )
}

function Panel({ title, total, share, children }) {
  return (
    <section className="rounded-2xl border border-line bg-white px-4 py-3.5">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line/70 pb-2">
        <h3 className={LABEL}>{title}</h3>
        <span className="text-[13px]">
          <strong className="font-display text-[17px] font-extrabold text-navy">
            {formatScore(total)}
          </strong>{' '}
          × {percent(share)} ={' '}
          <strong className="font-bold text-navy">{formatScore(total * share)}</strong>
        </span>
      </div>
      {children}
    </section>
  )
}

function CriteriaPanel({ scores }) {
  return (
    <Panel title="Criteria score" total={scores.criteria_score} share={CRITERIA_SHARE}>
      <ul>
        {DIMENSIONS.map(([key, label]) => {
          const dimension = scores.dimensions[key]
          return (
            <li
              key={key}
              className="grid gap-x-4 gap-y-1 border-t border-line/60 py-3 first:border-t-0 md:grid-cols-[11rem_minmax(8rem,12rem)_6.5rem_minmax(0,1fr)]"
            >
              <span className="text-[15px] font-semibold text-navy">{label}</span>
              <span className="flex items-center gap-3">
                <span className="w-8 font-display text-[15px] font-extrabold text-navy">
                  {dimension.score}
                </span>
                <Bar score={dimension.score} color="bg-success" className="flex-1" />
              </span>
              <span className="text-[13px]">
                × {percent(dimension.weight)} ={' '}
                <strong className="font-bold text-navy">
                  {formatScore(dimension.score * dimension.weight)}
                </strong>
              </span>
              <p className="text-sm">{dimension.justification}</p>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}

function AtsPanel({ ats }) {
  const keywords = [
    ...ats.keywords_found.map((word) => ({ word, found: true })),
    ...ats.keywords_missing.map((word) => ({ word, found: false })),
  ]
  return (
    <Panel title="ATS score" total={ats.score} share={ATS_SHARE}>
      <div className="grid gap-x-4 gap-y-1 py-3 md:grid-cols-[11rem_minmax(0,1fr)]">
        <span className="text-[15px] font-semibold text-navy">
          Keyword coverage {formatScore(ats.keyword_coverage)}
        </span>
        {keywords.length > 0 ? (
          <ul className="flex flex-wrap gap-1.5" aria-label="Keywords">
            {keywords.map(({ word, found }) => (
              <li
                key={word}
                className={`rounded-full px-2.5 py-0.5 text-[13px] font-semibold ${
                  found ? 'bg-success-soft text-success' : 'bg-mist text-body/70 line-through'
                }`}
              >
                {word}
                <span className="sr-only">{found ? ' (found)' : ' (missing)'}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm">The requirements have no keywords.</p>
        )}
      </div>
      <div className="grid gap-x-4 gap-y-1 border-t border-line/60 py-3 md:grid-cols-[11rem_minmax(0,1fr)]">
        <span className="text-[15px] font-semibold text-navy">
          Similarity {formatScore(ats.similarity)}
        </span>
        <p className="text-sm">How close the whole CV is in meaning to the job description.</p>
      </div>
    </Panel>
  )
}

// Why the candidate ranks where they do: the summary, then how the final
// score was made.
function Breakdown({ candidate, onShowEvidence }) {
  const { scores } = candidate
  return (
    <div className="flex flex-col gap-3 border-t border-line/60 bg-mist/60 px-5 pb-4 pt-3 lg:pl-24">
      {scores.summary && (
        <section className="rounded-2xl border-l-[3px] border-brand bg-white px-4 py-3.5 shadow-card">
          <h3 className={LABEL}>Why this rank</h3>
          <p className="mt-1.5 text-[15px] leading-relaxed text-navy">{scores.summary}</p>
        </section>
      )}
      <CriteriaPanel scores={scores} />
      {scores.ats && <AtsPanel ats={scores.ats} />}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <p className="text-sm">
          <strong className="font-bold text-navy">
            Final score {formatScore(scores.final_score)}
          </strong>{' '}
          = {formatScore(scores.criteria_score * CRITERIA_SHARE)} from criteria +{' '}
          {formatScore(scores.ats_score * ATS_SHARE)} from ATS
        </p>
        <button
          type="button"
          onClick={() => onShowEvidence(candidate.id)}
          className="flex min-h-10 items-center gap-1.5 text-[15px] font-semibold text-brand hover:text-brand-dark"
        >
          <ChevronRight className="size-4" aria-hidden="true" />
          See the evidence for each requirement
        </button>
      </div>
    </div>
  )
}

function RankedRow({ candidate, isOpen, onToggle, isLocked, onChanged, onShowEvidence }) {
  const Chevron = isOpen ? ChevronDown : ChevronRight
  const chip = candidate.status === 'shortlisted' ? SHORTLISTED_CHIP : SCORED_CHIP
  return (
    <li className="border-t border-line/60">
      <div className={`${ROW} py-3.5 ${isOpen ? 'bg-mist/60' : ''}`}>
        <RankBadge rank={candidate.scores.final_rank} />
        <button
          type="button"
          aria-expanded={isOpen}
          onClick={onToggle}
          className="flex min-h-10 min-w-0 items-center gap-3 text-left"
        >
          <Chevron className="size-4.5 shrink-0 text-body" aria-hidden="true" />
          <Initials name={candidate.full_name} />
          <span className="truncate text-[15px] font-semibold text-navy">{candidate.full_name}</span>
        </button>
        <FinalScore scores={candidate.scores} />
        <div className="hidden lg:block">
          <MatchCounts counts={candidate.match_counts} />
        </div>
        <div className="hidden lg:block">
          <StatusChip tone={chip.tone}>{chip.label}</StatusChip>
        </div>
        <RowActions chip={chip}>
          <ShortlistButton candidate={candidate} onChanged={onChanged} />
          <ViewCvLink candidateId={candidate.id} />
          <DeleteCandidateButton candidate={candidate} isLocked={isLocked} onDeleted={onChanged} />
        </RowActions>
      </div>
      {isOpen && <Breakdown candidate={candidate} onShowEvidence={onShowEvidence} />}
    </li>
  )
}

// Scored candidates ranked by final score. The interviewer shortlists them
// one by one or by a rule; the ranking itself never changes because of it.
export default function FinalRanking({ jobId, candidates, isLocked, onChanged, onShowEvidence }) {
  const [openId, setOpenId] = useState(null)
  const ranked = candidates
    .filter((item) => item.scores?.final_rank != null)
    .sort((a, b) => a.scores.final_rank - b.scores.final_rank)
  const unranked = candidates.filter((item) => item.scores?.final_rank == null)
  const shortlisted = candidates.filter((item) => item.status === 'shortlisted').length

  return (
    <section className="overflow-hidden rounded-card border border-line bg-white shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <h2 className="flex flex-wrap items-center gap-3 text-lg font-bold">
          <span>
            Final ranking <span className="font-semibold text-body">{ranked.length}</span>
          </span>
          {shortlisted > 0 && (
            <StatusChip tone={SHORTLISTED_CHIP.tone}>{shortlisted} shortlisted</StatusChip>
          )}
        </h2>
        <span className="text-[13px]">
          Final score = {percent(CRITERIA_SHARE)} criteria score + {percent(ATS_SHARE)} ATS score
        </span>
      </div>
      {ranked.length > 0 && (
        <ShortlistBar
          key={ranked.length}
          jobId={jobId}
          rankedCount={ranked.length}
          shortlistedCount={shortlisted}
          onChanged={onChanged}
        />
      )}
      <div className={`${ROW} bg-mist py-2.5`}>
        <span className={LABEL}>Rank</span>
        <span className={LABEL}>Candidate</span>
        <span className={LABEL}>Final score</span>
        <span className={`${LABEL} hidden lg:block`}>Requirements</span>
        <span className={`${LABEL} hidden lg:block`}>Status</span>
        <span className={`${LABEL} hidden text-right lg:block`}>Actions</span>
      </div>
      <ul>
        {ranked.map((candidate) => (
          <RankedRow
            key={candidate.id}
            candidate={candidate}
            isOpen={openId === candidate.id}
            onToggle={() => setOpenId(openId === candidate.id ? null : candidate.id)}
            isLocked={isLocked}
            onChanged={onChanged}
            onShowEvidence={onShowEvidence}
          />
        ))}
        {ranked.length === 0 && (
          <li className="border-t border-line/60 px-5 py-6 text-center text-[15px]">
            No candidate has been scored yet.
          </li>
        )}
      </ul>
      {unranked.length > 0 && (
        <>
          <div className={`${HEADING} border-t border-line/60 bg-mist`}>Not ranked</div>
          <ul>
            {unranked.map((candidate) => (
              <UnrankedRow
                key={candidate.id}
                candidate={candidate}
                grid={ROW}
                actions={
                  <>
                    <ViewCvLink candidateId={candidate.id} />
                    <DeleteCandidateButton
                      candidate={candidate}
                      isLocked={isLocked}
                      onDeleted={onChanged}
                    />
                  </>
                }
              />
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
