import { ArrowLeft, CircleAlert, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import Button from '../components/Button.jsx'
import Skeleton from '../components/Skeleton.jsx'
import SourceChip from '../components/assessment/SourceChip.jsx'
import { apiRequest } from '../lib/api.js'
import {
  COVERAGE,
  CV_RESULTS,
  REPORT_STATUS,
  SUITABILITY,
  bestOf,
  comparedIds,
  comparedRequirements,
  oneDecimal,
  readRanking,
} from '../lib/assessment.js'
import { shortDay } from '../lib/interviews.js'

const RANK_STYLES = [
  'bg-[#FFF4D6] text-[#8A5A00]',
  'bg-[#EEF1F6] text-[#44526B]',
  'bg-[#FBEBDD] text-[#8A4B00]',
]
const PRIORITIES = { must_have: 'Must-have', preferred: 'Preferred' }
const SHOWN_POINTS = 2

function Best() {
  return (
    <span className="rounded-full bg-success px-2 py-0.5 text-[11px] font-bold text-white">
      Best
    </span>
  )
}

function Row({ label, note, columns, cells, best = [] }) {
  return (
    <div className="grid border-b border-[#EEF2F9]" style={{ gridTemplateColumns: columns }}>
      <div className="border-r border-[#EEF2F9] bg-[#F8FAFE] px-4.5 py-3.5">
        <div className="text-sm font-semibold text-navy">{label}</div>
        {note && <div className="mt-0.5 text-[12.5px]">{note}</div>}
      </div>
      {cells.map((cell, index) => (
        <div
          key={index}
          className={`min-w-0 border-r border-[#EEF2F9] px-4.5 py-3.5 last:border-r-0 ${
            best[index] ? 'bg-[#F2FBF7]' : ''
          }`}
        >
          {cell}
        </div>
      ))}
    </div>
  )
}

function Section({ children }) {
  return (
    <div className="border-b border-line bg-mist px-4.5 py-2.5 text-xs font-bold uppercase tracking-wider text-[#6B7890]">
      {children}
    </div>
  )
}

function Score({ value, isBest, size = 'text-[15px]', note }) {
  return (
    <span className="flex flex-wrap items-center gap-2">
      <span className={`font-display font-extrabold tabular-nums text-navy ${size}`}>
        {oneDecimal(value) ?? '–'}
      </span>
      {note && <span className="text-xs">{note}</span>}
      {isBest && <Best />}
    </span>
  )
}

function Requirement({ entry }) {
  if (!entry) return <span className="text-[13px]">–</span>
  const status = COVERAGE[entry.status]
  const cv = entry.cv ? CV_RESULTS[entry.cv.status] : null
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${status.className}`}>
        {status.label}
      </span>
      {entry.average != null && (
        <span className="text-[12.5px] tabular-nums text-navy">
          avg {oneDecimal(entry.average)}
        </span>
      )}
      <span
        className={`rounded-full px-2 py-0.5 text-[11.5px] font-semibold ${
          cv ? cv.className : 'bg-mist text-body'
        }`}
      >
        {cv ? cv.label : 'Not screened'}
      </span>
    </span>
  )
}

function Points({ row, claims }) {
  if (!claims?.length) return <span className="text-[13px]">None.</span>
  return (
    <div className="flex flex-col gap-2.5">
      {claims.slice(0, SHOWN_POINTS).map((claim) => (
        <div key={claim.id} className="flex flex-col gap-1">
          <span className="text-[13.5px] text-navy">{claim.text}</span>
          <span className="flex flex-wrap gap-1">
            {claim.sources.map((source, index) => (
              <SourceChip key={index} sessionId={row.session_id} source={source} />
            ))}
          </span>
        </div>
      ))}
    </div>
  )
}

function Findings({ row }) {
  const gaps = row.gaps ?? []
  const areas = row.areas_to_verify ?? []
  return (
    <span className="text-[13.5px] leading-snug">
      <strong className="text-navy">
        {gaps.length} {gaps.length === 1 ? 'gap' : 'gaps'}
      </strong>{' '}
      · {areas.length} {areas.length === 1 ? 'area' : 'areas'} to verify
      {gaps[0] && <span className="mt-1 block">{gaps[0].text}</span>}
    </span>
  )
}

function Header({ row, canRemove, onRemove }) {
  const label = SUITABILITY[row.suitability]
  const status = REPORT_STATUS[row.status]
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <span
            className={`flex size-7.5 shrink-0 items-center justify-center rounded-[10px] font-display text-sm font-extrabold ${
              RANK_STYLES[row.rank - 1] ?? 'bg-mist text-[#6B7890]'
            }`}
          >
            {row.rank}
          </span>
          <span className="min-w-0">
            <span className="block truncate font-display text-base font-extrabold text-navy">
              {row.candidate_name}
            </span>
            <span className="text-[12.5px]">
              Interview {shortDay(row.started_at ?? row.scheduled_start)}
            </span>
          </span>
        </div>
        {canRemove && (
          <button
            type="button"
            aria-label={`Remove ${row.candidate_name} from the comparison`}
            onClick={onRemove}
            className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-[#9AA6BA] hover:bg-mist hover:text-navy"
          >
            <X className="size-4.5" aria-hidden="true" />
          </button>
        )}
      </div>
      <span className="flex flex-wrap gap-1.5">
        {label && (
          <span
            className={`rounded-full px-2.5 py-0.5 text-[12.5px] font-semibold ${label.className}`}
          >
            {label.label}
          </span>
        )}
        {status && (
          <span
            className={`rounded-full px-2.5 py-0.5 text-[12.5px] font-semibold ${status.className}`}
          >
            {row.status === 'draft' ? 'Draft' : 'Approved'}
          </span>
        )}
      </span>
      <Link
        to={`/app/interviews/${row.session_id}/assessment`}
        className="text-[13.5px] font-semibold text-brand hover:text-brand-dark"
      >
        Open report →
      </Link>
    </div>
  )
}

function LoadingCompare() {
  return (
    <div role="status" aria-label="Loading the comparison" className="flex flex-col gap-5">
      <Skeleton className="h-4 w-80" />
      <Skeleton className="h-9 w-96" />
      <Skeleton className="h-[480px] w-full rounded-[22px]" />
    </div>
  )
}

// Two or three ranked candidates of one job side by side: their scores
// (the best in each score row marked), requirement by requirement, and the
// top points of their reports. Read-only: nothing is decided here.
export default function ComparePage() {
  const { jobId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const ids = comparedIds(searchParams.get('ids'))
  const [job, setJob] = useState(null)
  const [ranking, setRanking] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let isCurrent = true
    Promise.all([apiRequest(`/jobs/${jobId}`), readRanking(jobId)])
      .then(([loadedJob, loadedRanking]) => {
        if (!isCurrent) return
        setJob(loadedJob)
        setRanking(loadedRanking)
      })
      .catch((loadError) => isCurrent && setError(loadError.message))
    return () => {
      isCurrent = false
    }
  }, [jobId])

  if (error) {
    return (
      <p role="alert" className="flex items-center gap-2 font-semibold text-danger">
        <CircleAlert className="size-5" aria-hidden="true" />
        {error}
      </p>
    )
  }
  if (!job || !ranking) {
    return (
      <div className="mx-auto max-w-6xl">
        <LoadingCompare />
      </div>
    )
  }

  const backTo = `/app/jobs/${job.id}/assessments`
  // Only ranked candidates can be compared, shown in rank order.
  const rows = ids
    .map((id) => ranking.find((row) => row.session_id === id && row.rank != null))
    .filter(Boolean)
    .sort((a, b) => a.rank - b.rank)

  function remove(sessionId) {
    const next = rows.map((row) => row.session_id).filter((id) => id !== sessionId)
    setSearchParams({ ids: next.join(',') }, { replace: true })
  }

  const columns = `210px repeat(${Math.max(rows.length, 1)}, minmax(0, 1fr))`
  const requirements = comparedRequirements(rows)
  const coverageOf = (row, id) => row.coverage_map?.find((entry) => entry.requirement_id === id)
  const best = {
    overall: bestOf(rows.map((row) => row.overall_score)),
    cv: bestOf(rows.map((row) => row.cv_score)),
    interview: bestOf(rows.map((row) => row.interview_score)),
    covered: bestOf(rows.map((row) => row.coverage?.covered ?? null)),
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-sm">
        <Link to="/app/jobs" className="font-semibold text-brand hover:text-brand-dark">
          Jobs
        </Link>
        <span aria-hidden="true">›</span>
        <Link to={`/app/jobs/${job.id}`} className="font-semibold text-brand hover:text-brand-dark">
          {job.title}
        </Link>
        <span aria-hidden="true">›</span>
        <Link to={backTo} className="font-semibold text-brand hover:text-brand-dark">
          Assessments
        </Link>
        <span aria-hidden="true">›</span>
        <span className="font-semibold text-navy">Compare</span>
      </nav>

      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-extrabold tracking-tight">Compare candidates</h1>
          <p className="mt-1.5 text-[14.5px]">
            {job.title} · {job.job_code} · {rows.length}{' '}
            {rows.length === 1 ? 'candidate' : 'candidates'} side by side. Read-only: nothing is
            decided here.
          </p>
        </div>
        <Button variant="outline" to={backTo}>
          <ArrowLeft className="size-4.5" aria-hidden="true" />
          Back to Assessments
        </Button>
      </header>

      {rows.length < 2 ? (
        <section className="flex max-w-xl flex-col gap-3.5 rounded-[20px] border border-dashed border-[#A9C8FF] bg-white p-5.5">
          <h2 className="text-lg font-extrabold text-navy">Pick at least 2 candidates</h2>
          <p className="text-sm leading-relaxed">
            On the Assessments tab, tick 2 or 3 ranked candidates and choose Compare. Only
            candidates with an overall score can be compared.
          </p>
          <div>
            <Button to={backTo}>Go to Assessments</Button>
          </div>
        </section>
      ) : (
        <>
          <p className="flex flex-wrap items-center gap-2 text-[13px]">
            <Best /> marks the highest score in each score row. Requirements show how the interview
            covered each one, with the CV result.
          </p>
          <div className="overflow-x-auto">
            <section className="min-w-[1000px] overflow-hidden rounded-[22px] border border-line bg-white shadow-card">
              <Row
                label="Candidate"
                columns={columns}
                cells={rows.map((row) => (
                  <Header
                    key={row.session_id}
                    row={row}
                    canRemove={rows.length > 2}
                    onRemove={() => remove(row.session_id)}
                  />
                ))}
              />
              <Section>Scores</Section>
              <Row
                label="Overall"
                note="40% CV + 60% interview"
                columns={columns}
                best={best.overall}
                cells={rows.map((row, index) => (
                  <Score
                    key={row.session_id}
                    value={row.overall_score}
                    isBest={best.overall[index]}
                    size="text-[22px]"
                  />
                ))}
              />
              <Row
                label="CV score"
                note="from screening"
                columns={columns}
                best={best.cv}
                cells={rows.map((row, index) => (
                  <Score key={row.session_id} value={row.cv_score} isBest={best.cv[index]} />
                ))}
              />
              <Row
                label="Interview score"
                note="average of the answers"
                columns={columns}
                best={best.interview}
                cells={rows.map((row, index) => (
                  <Score
                    key={row.session_id}
                    value={row.interview_score}
                    isBest={best.interview[index]}
                    note={`(${row.answers_evaluated} ${row.answers_evaluated === 1 ? 'answer' : 'answers'})`}
                  />
                ))}
              />
              <Row
                label="Requirements"
                note="covered in the interview"
                columns={columns}
                best={best.covered}
                cells={rows.map((row, index) => (
                  <span key={row.session_id} className="flex flex-wrap items-center gap-2 text-sm">
                    <span>
                      <strong className="text-navy">
                        {row.coverage?.covered ?? 0} of {row.coverage?.total ?? 0}
                      </strong>{' '}
                      covered
                    </span>
                    {best.covered[index] && <Best />}
                  </span>
                ))}
              />
              <Section>Requirement by requirement</Section>
              {requirements.map((entry) => (
                <Row
                  key={entry.requirement_id}
                  label={`${entry.requirement_id} ${entry.text}`}
                  note={PRIORITIES[entry.priority]}
                  columns={columns}
                  cells={rows.map((row) => (
                    <Requirement
                      key={row.session_id}
                      entry={coverageOf(row, entry.requirement_id)}
                    />
                  ))}
                />
              ))}
              <Section>From the reports</Section>
              <Row
                label="Top strengths"
                columns={columns}
                cells={rows.map((row) => (
                  <Points key={row.session_id} row={row} claims={row.strengths} />
                ))}
              />
              <Row
                label="Top weaknesses"
                columns={columns}
                cells={rows.map((row) => (
                  <Points key={row.session_id} row={row} claims={row.weaknesses} />
                ))}
              />
              <Row
                label="Gaps and areas to verify"
                columns={columns}
                cells={rows.map((row) => (
                  <Findings key={row.session_id} row={row} />
                ))}
              />
            </section>
          </div>
        </>
      )}
    </div>
  )
}
