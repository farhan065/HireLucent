import { useEffect, useState } from 'react'
import { apiRequest } from '../../lib/api.js'
import Button from '../Button.jsx'
import Markdown from '../chat/Markdown.jsx'
import RequirementChips from '../RequirementChips.jsx'
import SidePanel from '../SidePanel.jsx'
import WeightsBar from '../WeightsBar.jsx'

function Heading({ children }) {
  return (
    <h3 className="mt-6 text-[13px] font-semibold uppercase tracking-widest text-body">
      {children}
    </h3>
  )
}

// A read-only view of one saved job, opened from its dashboard card.
export default function JobDetailsPanel({ jobId, threadId, onClose }) {
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let isCurrent = true
    apiRequest(`/jobs/${jobId}`)
      .then((loaded) => isCurrent && setJob(loaded))
      .catch((loadError) => isCurrent && setError(loadError.message))
    return () => {
      isCurrent = false
    }
  }, [jobId])

  return (
    <SidePanel
      title={job ? `${job.title} · ${job.job_code}` : 'Job details'}
      onClose={onClose}
      footer={
        threadId && (
          <Button to={`/app/assistant/${threadId}`} className="w-full">
            Open conversation
          </Button>
        )
      }
    >
      {error && <p role="alert" className="font-semibold text-danger">{error}</p>}
      {!job && !error && <p role="status">Loading…</p>}
      {job && (
        <div className="text-[15px]">
          <Markdown>{job.jd_text}</Markdown>

          <Heading>Must-have</Heading>
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            <RequirementChips items={job.requirements.items} priority="must_have" />
          </div>

          <Heading>Preferred</Heading>
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            <RequirementChips items={job.requirements.items} priority="preferred" />
          </div>

          <Heading>Minimum experience</Heading>
          <p className="mt-2 font-semibold text-navy">
            {job.requirements.min_experience_years > 0
              ? `${job.requirements.min_experience_years} years`
              : 'No minimum'}
          </p>

          <Heading>Scoring weights</Heading>
          <div className="mt-2.5">
            <WeightsBar weights={job.scoring_weights} />
          </div>

          {job.post_url && (
            <>
              <Heading>Public post</Heading>
              <a href={job.post_url} className="mt-2 block font-semibold text-brand">
                {job.post_url}
              </a>
            </>
          )}
        </div>
      )}
    </SidePanel>
  )
}
