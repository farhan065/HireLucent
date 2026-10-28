import {
  Award,
  Briefcase,
  ChevronDown,
  Code,
  FileText,
  FolderKanban,
  Globe,
  GraduationCap,
  Mail,
  Shield,
  Target,
  UserRound,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useCandidatePhoto } from '../../hooks/useCandidatePhoto.js'
import { identityMessage } from '../../lib/identity.js'
import { openCv } from '../../lib/jobs.js'
import IdentityChip from '../interviews/IdentityChip.jsx'

const SKILLS_SHOWN = 8
const CHIP = 'rounded-full px-2.5 py-1 text-[12.5px] font-semibold'
const SMALL_CHIP = 'rounded-full bg-[#eef1f6] px-2 py-0.5 text-xs font-semibold text-[#44526b]'

// The LinkedIn and GitHub marks; Lucide has no brand icons.
function LinkedInIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-7a6 6 0 0 1 6-6z" />
      <rect x="2" y="9" width="4" height="12" />
      <circle cx="4" cy="4" r="2" />
    </svg>
  )
}

function GitHubIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.1-1.3-.3-2.5-1-3.5.3-1.2.3-2.4 0-3.5 0 0-1 0-3 1.5a13 13 0 0 0-8 0C6 2 5 2 5 2c-.3 1.2-.3 2.4 0 3.5A5.4 5.4 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.8.9-1.1 2.2-1 3.5v4" />
      <path d="M9 18c-4.5 2-5-2-7-2" />
    </svg>
  )
}

function linkIcon(href) {
  if (/linkedin\.com/i.test(href)) return LinkedInIcon
  if (/github\.com/i.test(href)) return GitHubIcon
  return Globe
}

function ContactRow({ icon: Icon, href, children }) {
  return (
    <a
      href={href}
      target={href.startsWith('mailto:') ? undefined : '_blank'}
      rel="noreferrer"
      className="flex min-h-9.5 items-center gap-2.5 text-[13.5px] font-semibold text-navy hover:text-brand"
    >
      <span className="flex size-7.5 shrink-0 items-center justify-center rounded-[9px] bg-mist text-brand">
        <Icon className="size-3.75" aria-hidden="true" />
      </span>
      <span className="min-w-0 break-all">{children}</span>
    </a>
  )
}

// One part of the CV that opens and closes, with how many items it holds.
function Section({ icon: Icon, title, count, isOpen, onToggle, children }) {
  return (
    <div className="border-t border-[#eef2f9] first:border-t-0">
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={onToggle}
        className={`flex min-h-12 w-full items-center gap-2.5 px-3.5 text-left font-display text-sm font-bold text-navy ${
          isOpen ? 'bg-mist' : 'bg-white hover:bg-mist/60'
        }`}
      >
        <Icon className="size-4 shrink-0 text-brand" aria-hidden="true" />
        <span className="flex-1">{title}</span>
        <span className="font-sans text-[12.5px] font-semibold text-body">{count}</span>
        <ChevronDown
          className={`size-4 shrink-0 text-body transition-transform ${isOpen ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>
      {isOpen && <div className="px-3.5 pb-3.5 pt-3">{children}</div>}
    </div>
  )
}

function Skills({ skills }) {
  const [isAll, setIsAll] = useState(false)
  const shown = isAll ? skills : skills.slice(0, SKILLS_SHOWN)
  const hidden = skills.length - shown.length
  return (
    <ul className="flex flex-wrap gap-1.5">
      {shown.map((skill) => (
        <li key={skill} className={`${CHIP} bg-tint text-brand-dark`}>
          {skill}
        </li>
      ))}
      {(hidden > 0 || isAll) && skills.length > SKILLS_SHOWN && (
        <li>
          <button
            type="button"
            onClick={() => setIsAll((all) => !all)}
            className={`${CHIP} min-h-7 border border-line bg-white font-bold text-body hover:text-navy`}
          >
            {isAll ? 'Show fewer' : `+${hidden} more`}
          </button>
        </li>
      )}
    </ul>
  )
}

// "Jan 2022" and "Present" become "Jan 2022 – Present".
function period(job) {
  return [job.start, job.end].filter(Boolean).join(' – ')
}

function Job({ job, isLast, startsOpen }) {
  const [isOpen, setIsOpen] = useState(startsOpen)
  return (
    <li className="grid grid-cols-[14px_minmax(0,1fr)] gap-3">
      <span className="flex flex-col items-center" aria-hidden="true">
        <span
          className={`mt-1 size-3 rounded-full ${startsOpen ? 'bg-brand' : 'border-2 border-brand'}`}
        />
        {!isLast && <span className="mt-1 w-0.5 flex-1 bg-line" />}
      </span>
      <div className={`flex flex-col items-start gap-1 ${isLast ? 'pb-1' : 'pb-4'}`}>
        <strong className="font-display text-[14.5px] font-bold text-navy">
          {job.title || 'Role not stated'}
        </strong>
        {job.company && <span className="text-[13px] font-semibold text-[#44526b]">{job.company}</span>}
        {period(job) && <span className={SMALL_CHIP}>{period(job)}</span>}
        {job.description &&
          (isOpen ? (
            <p className="mt-1 text-[13.5px] leading-relaxed text-navy">{job.description}</p>
          ) : (
            <button
              type="button"
              onClick={() => setIsOpen(true)}
              className="min-h-7 text-[13px] font-bold text-brand hover:text-brand-dark"
            >
              Show details
            </button>
          ))}
      </div>
    </li>
  )
}

const PROBE_STATUS = {
  partially_met: { label: 'Partly met', className: 'bg-warning-soft text-warning' },
  unmet: { label: 'Not met', className: 'bg-danger-soft text-danger' },
}

// Requirements the CV did not fully prove, from screening: what to ask about.
function AreasToProbe({ items }) {
  return (
    <ul className="flex flex-col gap-2.5">
      {items.map((item) => (
        <li key={item.id} className="flex flex-col gap-1">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11.5px] font-bold text-body">{item.id}</span>
            <strong className="text-[13.5px] font-semibold text-navy">{item.text}</strong>
            <span
              className={`rounded-full px-2 py-px text-[11px] font-bold ${PROBE_STATUS[item.status].className}`}
            >
              {PROBE_STATUS[item.status].label}
            </span>
          </span>
          {item.reason && <span className="text-[13px] leading-snug">{item.reason}</span>}
        </li>
      ))}
    </ul>
  )
}

// The identity check row (F7): the status chip and one short line. Before
// F7 an interview has no check, and the row says so.
function IdentityRow({ identity, hasPhoto }) {
  const isCalm = !identity || ['pending', 'verified', 'not_checked'].includes(identity.result)
  return (
    <div
      className={`flex flex-col gap-1.5 rounded-2xl border-[1.5px] px-3 py-2.5 ${
        identity?.result === 'pending' || !identity ? 'border-dashed' : ''
      } ${isCalm ? 'border-line' : identity.result === 'low' ? 'border-warning/40' : 'border-danger/40'}`}
    >
      <span className="flex items-center justify-between gap-2.5">
        <span className="flex items-center gap-2 text-[13.5px] font-semibold text-navy">
          <Shield className="size-4.25 text-body" aria-hidden="true" />
          Identity check
        </span>
        {identity ? (
          <IdentityChip identity={identity} />
        ) : (
          <span className="rounded-full bg-[#eef1f6] px-2.5 py-0.5 text-xs font-semibold text-[#44526b]">
            Not set up
          </span>
        )}
      </span>
      <span className="text-[12.5px] leading-snug text-body">
        {identity
          ? identityMessage(identity, hasPhoto)
          : 'This interview was scheduled before identity checks.'}
      </span>
    </div>
  )
}

// The application photo, larger, to compare with the live video.
function PhotoDialog({ url, name, onClose }) {
  useEffect(() => {
    function handleKey(event) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-navy/30 p-4"
      onClick={onClose}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Application photo"
        onClick={(event) => event.stopPropagation()}
        className="flex w-full max-w-105 animate-rise-in flex-col gap-3.5 rounded-card bg-white p-5 shadow-card"
      >
        <div className="flex items-center justify-between gap-2.5">
          <h2 className="text-lg font-extrabold">Application photo</h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="flex size-10 items-center justify-center rounded-xl text-body hover:bg-mist"
          >
            <X className="size-4.5" aria-hidden="true" />
          </button>
        </div>
        <img
          src={url}
          alt={`Application photo of ${name}`}
          className="aspect-square w-full rounded-2xl object-cover"
        />
        <p className="text-[13.5px] leading-normal">
          From the application form. Compare it with the live video. Only interviewers can see it;
          it is deleted with the application or the job.
        </p>
      </section>
    </div>
  )
}

function OpenCvButton({ candidateId }) {
  const [error, setError] = useState('')
  async function handleClick() {
    setError('')
    try {
      await openCv(candidateId)
    } catch (openError) {
      setError(openError.message)
    }
  }
  return (
    <div className="flex flex-col gap-1.5">
      <button
        type="button"
        onClick={handleClick}
        className="flex min-h-11 items-center justify-center gap-2 rounded-full border-[1.5px] border-[#c9dafb] bg-white font-display text-sm font-bold text-brand hover:border-brand"
      >
        <FileText className="size-4" aria-hidden="true" />
        Open the full CV
      </button>
      {error && (
        <p role="alert" className="text-center text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

// The candidate at a glance during the interview: who they are, the
// identity check, how to reach them, and the CV in parts that open on click,
// with the requirements to probe. Phone numbers are never stored, so they
// are not shown. The application photo replaces the placeholder when there
// is one.
export default function CandidateProfile({ candidate, identity = null }) {
  const [open, setOpen] = useState(() => new Set(['skills']))
  const [isPhotoOpen, setIsPhotoOpen] = useState(false)
  const photoUrl = useCandidatePhoto(candidate.id, candidate.has_photo)
  const probes = (candidate.requirement_matches ?? []).filter((item) => PROBE_STATUS[item.status])
  const facts = candidate.cv_facts ?? {}
  const skills = facts.skills ?? []
  const experience = facts.experience ?? []
  const education = facts.education ?? []
  const projects = facts.projects ?? []
  const certifications = facts.certifications ?? []
  const links = facts.links ?? []
  const years = facts.total_experience_years ?? 0
  const current =
    experience.find((job) => /present|current|now/i.test(job.end ?? '')) ?? experience[0]
  const scores = candidate.scores ?? {}

  function toggle(key) {
    setOpen((keys) => {
      const next = new Set(keys)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const sections = [
    skills.length > 0 && {
      key: 'skills',
      icon: Code,
      title: 'Technical skills',
      count: skills.length,
      body: <Skills skills={skills} />,
    },
    experience.length > 0 && {
      key: 'experience',
      icon: Briefcase,
      title: 'Work experience',
      count: years > 0 ? `${experience.length} · ${years} yrs` : experience.length,
      body: (
        <ol>
          {experience.map((job, index) => (
            <Job
              key={`${job.title}-${job.company}-${index}`}
              job={job}
              isLast={index === experience.length - 1}
              startsOpen={index === 0}
            />
          ))}
        </ol>
      ),
    },
    education.length > 0 && {
      key: 'education',
      icon: GraduationCap,
      title: 'Education',
      count: education.length,
      body: (
        <ul className="flex flex-col gap-2">
          {education.map((study, index) => (
            <li key={`${study.degree}-${index}`} className="flex flex-col gap-0.5 rounded-2xl bg-mist p-3">
              <strong className="font-display text-sm font-bold text-navy">
                {[study.degree, study.field].filter(Boolean).join(' in ') || 'Study'}
              </strong>
              <span className="text-[13px]">
                {[study.institution, study.year].filter(Boolean).join(' · ')}
              </span>
            </li>
          ))}
        </ul>
      ),
    },
    projects.length > 0 && {
      key: 'projects',
      icon: FolderKanban,
      title: 'Projects',
      count: projects.length,
      body: (
        <ul className="flex flex-col gap-2.5">
          {projects.map((project, index) => (
            <li
              key={`${project.name}-${index}`}
              className="flex flex-col gap-1.5 rounded-2xl border border-line p-3"
            >
              <strong className="font-display text-sm font-bold text-navy">
                {project.name || 'Project'}
              </strong>
              {project.description && (
                <p className="text-[13.5px] leading-normal text-navy">{project.description}</p>
              )}
              {project.technologies?.length > 0 && (
                <span className="flex flex-wrap gap-1.25">
                  {project.technologies.map((technology) => (
                    <span key={technology} className={SMALL_CHIP}>
                      {technology}
                    </span>
                  ))}
                </span>
              )}
            </li>
          ))}
        </ul>
      ),
    },
    probes.length > 0 && {
      key: 'probe',
      icon: Target,
      title: 'Areas to probe',
      count: probes.length,
      body: <AreasToProbe items={probes} />,
    },
    certifications.length > 0 && {
      key: 'certifications',
      icon: Award,
      title: 'Certifications',
      count: certifications.length,
      body: (
        <ul className="flex flex-col gap-1.5 text-[13.5px] text-navy">
          {certifications.map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ul>
      ),
    },
  ].filter(Boolean)

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4.5 [&>*]:shrink-0">
        <div className="flex items-center gap-3.5">
          {photoUrl ? (
            <button
              type="button"
              aria-label="Open the application photo"
              onClick={() => setIsPhotoOpen(true)}
              className="size-16 shrink-0 cursor-zoom-in overflow-hidden rounded-[18px] border-[1.5px] border-line"
            >
              <img src={photoUrl} alt="" className="size-full object-cover" />
            </button>
          ) : (
            <span
              role="img"
              aria-label="Photo placeholder"
              className="flex size-16 shrink-0 items-end justify-center overflow-hidden rounded-[18px] bg-teal-soft"
            >
              <UserRound
                className="-mb-1.5 size-14 fill-[#9cc9dd] text-[#9cc9dd]"
                aria-hidden="true"
              />
            </span>
          )}
          <div className="flex min-w-0 flex-col gap-0.5">
            <h2 className="text-lg font-extrabold tracking-tight">{candidate.full_name}</h2>
            {current && (
              <span className="text-[13.5px]">
                {[current.title, current.company].filter(Boolean).join(' · ')}
              </span>
            )}
            <span className="mt-1 flex flex-wrap gap-1.5">
              {scores.final_score != null && (
                <span className={`${CHIP} bg-tint py-0.5 font-bold text-brand-dark`}>
                  Score {Math.round(scores.final_score)}
                </span>
              )}
              {scores.final_rank && (
                <span className={`${CHIP} bg-success-soft py-0.5 font-bold text-success`}>
                  Rank {scores.final_rank}
                </span>
              )}
            </span>
          </div>
        </div>

        <IdentityRow identity={identity} hasPhoto={Boolean(photoUrl)} />

        <div className="flex flex-col">
          <h3 className="mb-1 font-sans text-xs font-semibold uppercase tracking-wider text-body">
            Contact
          </h3>
          <ContactRow icon={Mail} href={`mailto:${candidate.email}`}>
            {candidate.email}
          </ContactRow>
          {links.map((link) => (
            <ContactRow
              key={link}
              icon={linkIcon(link)}
              href={/^https?:\/\//i.test(link) ? link : `https://${link}`}
            >
              {link.replace(/^https?:\/\//i, '').replace(/^www\./i, '')}
            </ContactRow>
          ))}
        </div>

        {sections.length > 0 ? (
          <div className="overflow-hidden rounded-2xl border border-line">
            {sections.map((section) => (
              <Section
                key={section.key}
                icon={section.icon}
                title={section.title}
                count={section.count}
                isOpen={open.has(section.key)}
                onToggle={() => toggle(section.key)}
              >
                {section.body}
              </Section>
            ))}
          </div>
        ) : (
          <p className="text-sm">No skills, work history or education could be read from the CV.</p>
        )}
      </div>
      <div className="border-t border-line px-4.5 py-3">
        <OpenCvButton candidateId={candidate.id} />
      </div>
      {isPhotoOpen && photoUrl && (
        <PhotoDialog
          url={photoUrl}
          name={candidate.full_name}
          onClose={() => setIsPhotoOpen(false)}
        />
      )}
    </div>
  )
}
