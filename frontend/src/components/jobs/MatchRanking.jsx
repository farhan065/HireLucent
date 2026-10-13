import { ChevronDown, ChevronRight, CircleCheck, CircleMinus, CircleX } from 'lucide-react'
import { useEffect, useState } from 'react'
import StatusChip from '../StatusChip.jsx'
import { canOpenUnranked } from '../../lib/results.js'
import { UnrankedDetails } from './CvFacts.jsx'
import DeleteCandidateButton from './DeleteCandidateButton.jsx'
import {
  FilterNote,
  HEADING,
  Initials,
  LABEL,
  NoMatches,
  RowActions,
  UnrankedRow,
  ViewCvLink,
} from './candidates.jsx'
import { INTERVIEW_CHIP, SHORTLISTED_CHIP } from '../../lib/jobs.js'

const ROW = 'grid grid-cols-[3.25rem_minmax(0,1.6fr)_minmax(0,1fr)] items-center gap-x-4 gap-y-2 px-5 lg:grid-cols-[3.25rem_minmax(0,1.6fr)_minmax(9rem,1fr)_minmax(0,1.3fr)_10.5rem_9.5rem]'

const RESULTS = {
  met: { label: 'Met', tone: 'success', icon: CircleCheck, color: 'text-success', line: 'border-success' },
  partially_met: {
    label: 'Partly met',
    tone: 'warning',
    icon: CircleMinus,
    color: 'text-warning',
    line: 'border-warning',
  },
  unmet: { label: 'Not met', tone: 'danger', icon: CircleX, color: 'text-danger', line: 'border-danger' },
}

// The requirement match of one candidate as three small counts.
export function MatchCounts({ counts }) {
  if (!counts) return <span className="text-sm">–</span>
  const parts = [
    ['met', 'met', 'bg-success-soft text-success'],
    ['partially_met', 'partly', 'bg-warning-soft text-warning'],
    ['unmet', 'not met', 'bg-danger-soft text-danger'],
  ]
  return (
    <div className="flex flex-wrap gap-1.5">
      {parts.map(([key, label, style]) => (
        <span key={key} className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${style}`}>
          {counts[key]} {label}
        </span>
      ))}
    </div>
  )
}

function MatchBar({ score }) {
  const color = score >= 75 ? 'bg-success' : score >= 50 ? 'bg-brand' : 'bg-warning'
  return (
    <div className="flex items-center gap-2.5">
      <span className="w-12 font-display text-[17px] font-extrabold text-navy">
        {Math.round(score)}%
      </span>
      <div className="hidden h-1.5 min-w-16 flex-1 overflow-hidden rounded-full bg-tint sm:block">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

export function RankBadge({ rank }) {
  return (
    <span
      className={`flex size-8 items-center justify-center rounded-[10px] font-display text-sm font-extrabold ${
        rank === 1 ? 'bg-brand text-white' : 'bg-tint text-brand-dark'
      }`}
    >
      #{rank}
    </span>
  )
}

// One requirement with its result, the evidence quoted from the CV and the reason.
function RequirementResult({ item }) {
  const result = RESULTS[item.status]
  const Icon = result.icon
  return (
    <li className="flex gap-3.5 border-t border-line/70 py-3.5">
      <Icon className={`mt-0.5 size-5.5 shrink-0 ${result.color}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-[13px] font-bold">{item.id}</span>
          <span className="text-[15px] font-semibold text-navy">{item.text}</span>
          <StatusChip tone={item.priority === 'must_have' ? 'info' : 'neutral'}>
            {item.priority === 'must_have' ? 'Must-have' : 'Preferred'}
          </StatusChip>
          <span className="ml-auto">
            <StatusChip tone={result.tone}>{result.label}</StatusChip>
          </span>
        </div>
        {item.evidence ? (
          <blockquote
            className={`mt-1.5 rounded-r-xl border-l-[3px] bg-white px-3 py-2 text-sm italic text-navy ${result.line}`}
          >
            “{item.evidence}”
            {!item.evidence_in_cv && (
              <span className="ml-2 text-xs font-semibold not-italic text-warning">
                not found word for word in the CV
              </span>
            )}
          </blockquote>
        ) : (
          <p className="mt-1.5 text-sm text-body/80">No evidence in the CV.</p>
        )}
        {item.reason && <p className="mt-1.5 text-sm">{item.reason}</p>}
      </div>
    </li>
  )
}

function Evidence({ matches }) {
  const ordered = [...matches].sort(
    (a, b) => (a.priority === 'must_have' ? 0 : 1) - (b.priority === 'must_have' ? 0 : 1),
  )
  return (
    <div className="border-t border-line/60 bg-mist/60 px-5 pb-4 pt-1.5 lg:pl-24">
      <div className="flex flex-wrap items-center justify-between gap-2 py-2.5">
        <span className={LABEL}>Requirements, must-haves first</span>
        <span className="text-[13px]">
          Match score: met counts 1, partly met 0.5, must-haves count double
        </span>
      </div>
      <ul>
        {ordered.map((item) => (
          <RequirementResult key={item.id} item={item} />
        ))}
      </ul>
    </div>
  )
}


function RankedRow({ candidate, isOpen, onToggle, isLocked, onChanged }) {
  const Chevron = isOpen ? ChevronDown : ChevronRight
  const chip =
    candidate.status === 'interview_scheduled'
      ? INTERVIEW_CHIP
      : candidate.status === 'shortlisted'
        ? SHORTLISTED_CHIP
        : { tone: 'success', label: candidate.scores ? 'Scored' : 'Matched' }
  return (
    <li id={`match-${candidate.id}`} className="scroll-mt-6 border-t border-line/60">
      <div className={`${ROW} py-3.5 ${isOpen ? 'bg-mist/60' : ''}`}>
        <RankBadge rank={candidate.rank} />
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
        <MatchBar score={candidate.match_score} />
        <div className="hidden lg:block">
          <MatchCounts counts={candidate.match_counts} />
        </div>
        <div className="hidden lg:block">
          <StatusChip tone={chip.tone}>{chip.label}</StatusChip>
        </div>
        <RowActions chip={chip}>
          <ViewCvLink candidateId={candidate.id} />
          <DeleteCandidateButton candidate={candidate} isLocked={isLocked} onDeleted={onChanged} />
        </RowActions>
      </div>
      {isOpen && <Evidence matches={candidate.requirement_matches} />}
    </li>
  )
}

function byMatchRank(list) {
  return list.filter((item) => item.rank != null).sort((a, b) => a.rank - b.rank)
}

// Matched candidates ranked by match score, with the evidence for each
// requirement one click away. Candidates without a rank are listed below.
// initialOpenId opens one candidate, for example when the final ranking
// links here. "visible" is the part the Show filter and the search leave;
// ranks keep their real numbers.
export default function MatchRanking({
  candidates,
  visible = candidates,
  isFiltered = false,
  onShowAll,
  initialOpenId = null,
  isLocked,
  onChanged,
}) {
  const [openId, setOpenId] = useState(initialOpenId)
  const rankedCount = byMatchRank(candidates).length
  const ranked = byMatchRank(visible)
  const unranked = visible.filter((item) => item.rank == null)
  const isEmpty = isFiltered && visible.length === 0

  useEffect(() => {
    if (initialOpenId) {
      document.getElementById(`match-${initialOpenId}`)?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [initialOpenId])

  return (
    <section className="overflow-hidden rounded-card border border-line bg-white shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <h2 className="flex flex-wrap items-center gap-3 text-lg font-bold">
          <span>
            Ranking by requirement match{' '}
            <span className="font-semibold text-body">{rankedCount}</span>
          </span>
          {isFiltered && (
            <FilterNote shown={visible.length} total={candidates.length} onShowAll={onShowAll} />
          )}
        </h2>
        <span className="text-[13px]">
          Match score: how well each CV meets the requirements, by meaning
        </span>
      </div>
      <div className={`${ROW} bg-mist py-2.5`}>
        <span className={LABEL}>Rank</span>
        <span className={LABEL}>Candidate</span>
        <span className={LABEL}>Match</span>
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
          />
        ))}
        {isEmpty && <NoMatches onShowAll={onShowAll} />}
        {ranked.length === 0 && !isFiltered && (
          <li className="border-t border-line/60 px-5 py-6 text-center text-[15px]">
            No candidate has been matched yet.
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
                details={
                  canOpenUnranked(candidate) ? <UnrankedDetails candidate={candidate} /> : null
                }
                isOpen={openId === candidate.id}
                onToggle={() => setOpenId(openId === candidate.id ? null : candidate.id)}
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
