import { Award, Briefcase, Code, FolderKanban, GraduationCap, Link } from 'lucide-react'
import { LABEL } from './candidates.jsx'

function Section({ icon: Icon, title, children }) {
  return (
    <div className="mt-4">
      <h4 className={`${LABEL} flex items-center gap-2 text-body`}>
        <Icon className="size-4 text-brand" aria-hidden="true" />
        {title}
      </h4>
      <div className="mt-2">{children}</div>
    </div>
  )
}

// "Jan 2022" and "Present" become "Jan 2022 – Present".
function period(job) {
  return [job.start, job.end].filter(Boolean).join(' – ')
}

// A link from the CV, opened in a new tab. Links without a scheme get https.
function CvLink({ href }) {
  const url = /^https?:\/\//i.test(href) ? href : `https://${href}`
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="flex min-h-8 items-center gap-1.5 break-all text-sm font-semibold text-brand hover:text-brand-dark"
    >
      <Link className="size-4 shrink-0" aria-hidden="true" />
      {href.replace(/^https?:\/\//i, '')}
    </a>
  )
}

// What the AI read from the CV: skills, work history, education,
// certifications, projects and links. Email addresses and phone numbers are
// not part of it. Empty sections are left out.
export default function CvFacts({ facts }) {
  const years = facts.total_experience_years ?? 0
  const skills = facts.skills ?? []
  const experience = facts.experience ?? []
  const education = facts.education ?? []
  const certifications = facts.certifications ?? []
  const projects = facts.projects ?? []
  const links = facts.links ?? []
  const isEmpty = [skills, experience, education, certifications, projects, links].every(
    (list) => list.length === 0,
  )

  return (
    <section className="rounded-2xl border border-line bg-white px-4 py-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className={LABEL}>CV facts</h3>
        {years > 0 && (
          <span className="rounded-xl bg-success-soft px-3 py-1 text-[13px] font-semibold text-success">
            <strong className="font-display text-base">{years}</strong>{' '}
            {years === 1 ? 'year' : 'years'} of experience
          </span>
        )}
      </div>
      <p className="mt-1 text-[13px] text-body/80">
        What the AI read from the CV. Phone numbers are not shown.
      </p>
      {isEmpty && <p className="mt-3 text-sm">No skills, work history or education could be read.</p>}

      <div className="grid gap-x-8 md:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div>
          {skills.length > 0 && (
            <Section icon={Code} title="Skills">
              <ul className="flex flex-wrap gap-1.5">
                {skills.map((skill) => (
                  <li
                    key={skill}
                    className="rounded-full bg-tint px-2.5 py-0.5 text-[13px] font-semibold text-brand-dark"
                  >
                    {skill}
                  </li>
                ))}
              </ul>
            </Section>
          )}
          {experience.length > 0 && (
            <Section icon={Briefcase} title="Work history">
              <ol>
                {experience.map((job, index) => (
                  <li key={`${job.title}-${job.company}-${index}`} className="flex gap-3">
                    <div className="flex flex-col items-center" aria-hidden="true">
                      <span className="mt-1.5 size-2.5 rounded-full bg-brand" />
                      {index < experience.length - 1 && <span className="mt-1 w-0.5 flex-1 bg-line" />}
                    </div>
                    <div className="min-w-0 flex-1 pb-3.5">
                      <p className="text-[15px] font-bold text-navy">
                        {job.title || 'Role not stated'}
                        {job.company && <span className="font-medium text-body"> · {job.company}</span>}
                      </p>
                      {period(job) && <p className="text-xs text-body/80">{period(job)}</p>}
                      {job.description && <p className="mt-1 text-sm leading-relaxed">{job.description}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            </Section>
          )}
        </div>

        <div>
          {education.length > 0 && (
            <Section icon={GraduationCap} title="Education">
              <ul className="flex flex-col gap-1.5 text-sm">
                {education.map((study, index) => (
                  <li key={`${study.degree}-${index}`}>
                    <strong className="font-semibold text-navy">
                      {[study.degree, study.field].filter(Boolean).join(' in ') || 'Study'}
                    </strong>
                    {[study.institution, study.year].filter(Boolean).map((part) => ` · ${part}`)}
                  </li>
                ))}
              </ul>
            </Section>
          )}
          {certifications.length > 0 && (
            <Section icon={Award} title="Certifications">
              <ul className="flex flex-col gap-1 text-sm">
                {certifications.map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            </Section>
          )}
          {projects.length > 0 && (
            <Section icon={FolderKanban} title="Projects">
              <ul className="flex flex-col gap-2 text-sm">
                {projects.map((project, index) => (
                  <li key={`${project.name}-${index}`}>
                    <strong className="font-semibold text-navy">{project.name || 'Project'}</strong>
                    {project.description && `: ${project.description}`}
                    {project.technologies?.length > 0 && (
                      <span className="text-body/80">
                        {' '}
                        Technologies: {project.technologies.join(', ')}.
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </Section>
          )}
          {links.length > 0 && (
            <Section icon={Link} title="Links">
              <div className="flex flex-col items-start">
                {links.map((href) => (
                  <CvLink key={href} href={href} />
                ))}
              </div>
            </Section>
          )}
        </div>
      </div>
    </section>
  )
}

// What an opened row under "Not ranked" shows: for an excluded candidate
// every reason first, then the CV facts, so the two can be compared.
export function UnrankedDetails({ candidate }) {
  const reasons =
    candidate.status === 'excluded' ? (candidate.excluded_reason ?? '').split('\n').filter(Boolean) : []
  return (
    <>
      {reasons.length > 0 && (
        <section className="rounded-2xl border-l-[3px] border-warning bg-white px-4 py-3.5">
          <h3 className={`${LABEL} text-warning`}>Why excluded</h3>
          <ul className="mt-1.5 list-disc pl-5 text-[15px] leading-relaxed text-navy">
            {reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <p className="mt-1.5 text-[13px] text-body/80">
            Excluded candidates are not matched or scored. Compare the reasons with the CV facts
            below.
          </p>
        </section>
      )}
      <CvFacts facts={candidate.cv_facts} />
    </>
  )
}
