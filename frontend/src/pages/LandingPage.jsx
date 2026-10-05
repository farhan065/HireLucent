import { ArrowRight } from 'lucide-react'
import Button from '../components/Button.jsx'
import Logo from '../components/Logo.jsx'
import StatusChip from '../components/StatusChip.jsx'

const NAV_LINKS = [
  { href: '#how', label: 'How it works' },
  { href: '#principles', label: 'Principles' },
]

const STEPS = [
  {
    stage: 'Pre-interview',
    title: 'Create and publish the job',
    text: 'Describe the role in chat. The assistant drafts the job description and posts it once you approve.',
  },
  {
    stage: 'Pre-interview',
    title: 'Screen and shortlist',
    text: 'CVs are collected, matched to the requirements, scored and ranked, each with supporting evidence.',
  },
  {
    stage: 'During interview',
    title: 'Live video interview',
    text: 'Meet the candidate in the browser while a speaker-labelled transcript is captured as you talk.',
  },
  {
    stage: 'Post-interview',
    title: 'Assess and decide',
    text: 'Answers are evaluated and merged with the CV results into one report. The final decision is yours.',
  },
]

const PRINCIPLES = [
  {
    title: 'Traceable to evidence',
    text: 'Every score and flag links to the CV line or transcript moment behind it.',
  },
  {
    title: 'Human approval first',
    text: 'Publishing a job, sending invites and approving a report all wait for you.',
  },
  {
    title: 'Private by design',
    text: 'Raw audio and video are never stored, and only job-related criteria are scored.',
  },
]

// Illustrative values for the product preview card in the hero.
const SAMPLE_SCORES = [
  { label: 'Technical skills', value: 90 },
  { label: 'Relevant experience', value: 82 },
  { label: 'Qualifications', value: 78 },
  { label: 'ATS match', value: 88 },
]

function Eyebrow({ children }) {
  return (
    <span className="text-[13px] font-semibold uppercase tracking-widest text-brand">
      {children}
    </span>
  )
}

function Header() {
  return (
    <header className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-5 px-6 py-5">
      <Logo />
      <nav aria-label="Main" className="flex flex-wrap gap-8 text-[15px] font-semibold text-navy">
        {NAV_LINKS.map((link) => (
          <a key={link.href} href={link.href} className="hover:text-brand">
            {link.label}
          </a>
        ))}
      </nav>
      <Button to="/login">Sign in</Button>
    </header>
  )
}

function SampleCandidateCard() {
  return (
    <div className="relative flex w-full max-w-md flex-col gap-4 rounded-[26px] border border-line bg-white p-7 shadow-[0_30px_60px_rgb(11_31_75/0.12)]">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest">Sample candidate</p>
          <p className="font-display text-xl font-bold text-navy">Candidate A</p>
        </div>
        <div className="flex size-16 items-center justify-center rounded-full bg-brand font-display text-2xl font-extrabold text-white">
          86
        </div>
      </div>
      {SAMPLE_SCORES.map((score) => (
        <div key={score.label} className="flex flex-col gap-1.5">
          <div className="flex justify-between text-sm">
            <span>{score.label}</span>
            <span className="font-semibold text-navy">{score.value}</span>
          </div>
          <div className="h-2 rounded-full bg-tint">
            <div className="h-2 rounded-full bg-brand" style={{ width: `${score.value}%` }} />
          </div>
        </div>
      ))}
      <div className="flex flex-col gap-2 rounded-2xl bg-mist p-4">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold text-navy">Python web development</span>
          <StatusChip tone="success">Met</StatusChip>
        </div>
        <p className="text-sm leading-relaxed text-navy">
          “Built REST services in <mark className="rounded bg-[#dce8ff] px-1 text-navy">Django</mark>
          …” <span className="text-body">· CV, work history</span>
        </p>
      </div>
    </div>
  )
}

function Hero() {
  return (
    <section className="mx-4 rounded-4xl bg-mist bg-[radial-gradient(700px_420px_at_88%_8%,#e3e8ff_0%,transparent_70%)] md:mx-6">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-14 px-6 py-16 md:px-8 md:py-20">
        <div className="flex flex-1 basis-110 flex-col items-start gap-6">
          <span className="rounded-full border border-line bg-white px-3.5 py-2 text-[13px] font-semibold text-brand-dark">
            AI-powered recruitment and interview intelligence
          </span>
          <h1 className="text-4xl font-extrabold leading-[1.08] tracking-tight md:text-[58px]">
            Hire with clarity. Decide with <span className="text-brand">evidence</span>.
          </h1>
          <p className="max-w-xl text-lg leading-relaxed">
            HireLucent screens CVs, runs the live interview and turns both into one assessment
            where every score points back to what the candidate wrote or said.
          </p>
          <div className="flex flex-wrap items-center gap-5">
            <Button to="/login" className="min-h-13.5 px-8 text-base">
              Sign in to your workspace
            </Button>
            <a href="#how" className="inline-flex items-center gap-1.5 font-semibold text-navy hover:text-brand">
              See how it works <ArrowRight className="size-4" aria-hidden="true" />
            </a>
          </div>
        </div>
        <div className="relative flex flex-1 basis-105 justify-center">
          {/* Decorative light rings behind the card. */}
          <svg
            viewBox="0 0 520 520"
            aria-hidden="true"
            className="absolute -top-16 right-0 w-130 max-w-full"
          >
            <g fill="none" stroke="#1557e0" strokeOpacity="0.13">
              {[90, 140, 190, 240].map((radius) => (
                <circle key={radius} cx="300" cy="230" r={radius} />
              ))}
            </g>
          </svg>
          <SampleCandidateCard />
        </div>
      </div>
    </section>
  )
}

function HowItWorks() {
  return (
    <section id="how" className="mx-auto flex max-w-6xl scroll-mt-6 flex-col gap-10 px-6 py-20">
      <div className="flex max-w-2xl flex-col gap-3">
        <Eyebrow>How it works</Eyebrow>
        <h2 className="text-3xl font-extrabold leading-tight tracking-tight md:text-[40px]">
          One workflow, from job post to hiring decision
        </h2>
      </div>
      <ol className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step, index) => (
          <li
            key={step.title}
            className="flex flex-col gap-3 rounded-card border border-line bg-white p-7 shadow-card"
          >
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-tint font-display font-extrabold text-brand">
                {index + 1}
              </span>
              <span className="text-xs font-semibold uppercase tracking-widest">{step.stage}</span>
            </div>
            <h3 className="text-xl font-bold">{step.title}</h3>
            <p className="text-[15px] leading-relaxed">{step.text}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}

function Principles() {
  return (
    <section id="principles" className="mx-4 mb-12 scroll-mt-6 rounded-4xl bg-royal md:mx-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-9 px-6 py-16 md:px-10">
        <h2 className="text-3xl font-extrabold tracking-tight text-white md:text-4xl">
          AI assists. People decide.
        </h2>
        <div className="grid gap-10 md:grid-cols-3">
          {PRINCIPLES.map((principle) => (
            <div key={principle.title} className="flex flex-col gap-2.5">
              <h3 className="text-xl font-bold text-white">{principle.title}</h3>
              <p className="text-[15px] leading-relaxed text-[#d5e2ff]">{principle.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default function LandingPage() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <HowItWorks />
        <Principles />
      </main>
      <footer className="mx-auto flex max-w-6xl flex-wrap justify-between gap-4 px-6 pb-10 pt-2 text-sm">
        <span>HireLucent · Bringing clarity and intelligence to candidate evaluation.</span>
        <span>BJIT Academy AI Trainee final project</span>
      </footer>
    </>
  )
}