import {
  ArrowRight,
  Check,
  ChartLine,
  Clock,
  FileText,
  Link2,
  LockKeyhole,
  Mail,
  MessageSquare,
  SearchCheck,
  UserRound,
  Video,
} from 'lucide-react'
import Button from '../components/Button.jsx'
import Logo from '../components/Logo.jsx'
import StatusChip from '../components/StatusChip.jsx'

const NAV_LINKS = [
  { href: '#how', label: 'How it works' },
  { href: '#features', label: 'Features' },
  { href: '#principles', label: 'Principles' },
]

const HERO_POINTS = [
  'Every score traceable',
  'You approve every action',
  'Raw audio and video never stored',
]

// The four stages, in the colours used on the architecture diagrams.
const STEPS = [
  {
    stage: 'Pre-interview',
    title: 'Create and publish the job',
    text: 'Describe the role in chat. The assistant drafts the job description and posts it once you approve.',
    color: '#2563eb',
    label: 'text-[#2563eb]',
  },
  {
    stage: 'Pre-interview',
    title: 'Screen and shortlist',
    text: 'CVs are matched to the requirements, scored and ranked with evidence. You choose who goes forward.',
    color: '#7c3aed',
    label: 'text-[#6d28d9]',
  },
  {
    stage: 'During interview',
    title: 'Live video interview',
    text: 'Meet the candidate in the browser while a speaker-labelled transcript is written as you talk.',
    color: '#059669',
    label: 'text-[#047857]',
  },
  {
    stage: 'Post-interview',
    title: 'Assess and decide',
    text: 'Answers are evaluated and merged with the CV results into one report. The final decision is yours.',
    color: '#ea580c',
    label: 'text-[#c2410c]',
  },
]

const FEATURES = [
  {
    icon: FileText,
    tint: 'bg-[#dbeafe] text-[#2563eb]',
    title: 'Evidence-based CV screening',
    text: 'Every requirement marked met, partly met or not met, with the CV line that proves it.',
  },
  {
    icon: Video,
    tint: 'bg-[#d1fae5] text-[#059669]',
    title: 'Live interview and transcript',
    text: 'Browser video with a PIN and photo check, and a transcript that labels who said what.',
  },
  {
    icon: MessageSquare,
    tint: 'bg-[#ede9fe] text-[#7c3aed]',
    title: 'Q&A analysis with references',
    text: 'Each answer judged with a quote, and checked against your own reference documents.',
  },
  {
    icon: ChartLine,
    tint: 'bg-[#ffedd5] text-[#ea580c]',
    title: 'Scores, ranking and comparison',
    text: 'CV and interview scores in one ranked list, with six interview dimensions and side-by-side compare.',
  },
  {
    icon: SearchCheck,
    tint: 'bg-[#fce7f3] text-[#db2777]',
    title: 'CV claims and interview quality',
    text: 'Points to check before deciding, and tips to run the next interview better.',
  },
  {
    icon: Mail,
    tint: 'bg-[#e0f2fe] text-[#0284c7]',
    title: 'Personal feedback emails',
    text: 'A fair, personal email for every candidate, sent only after you approve it.',
  },
]

const PRINCIPLES = [
  {
    icon: Link2,
    title: 'Traceable to evidence',
    text: 'Every score and flag links to the CV line or transcript moment behind it.',
  },
  {
    icon: UserRound,
    title: 'Human approval first',
    text: 'Publishing a job, sending invites, approving a report and sending emails all wait for you.',
  },
  {
    icon: LockKeyhole,
    title: 'Private by design',
    text: 'Raw audio and video are never stored, and only job-related criteria are scored.',
  },
]

// Illustrative values for the product preview card and the tour.
const SAMPLE_SCORES = [
  { label: 'Technical skills', value: 90 },
  { label: 'Relevant experience', value: 82 },
  { label: 'Qualifications', value: 78 },
  { label: 'Interview performance', value: 84, violet: true },
]

const SAMPLE_RANKING = [
  { name: 'Candidate A', score: 88, status: 'Shortlisted', tone: 'success' },
  { name: 'Candidate B', score: 79, status: 'Shortlisted', tone: 'success' },
  { name: 'Candidate C', score: 66, status: 'Screened', tone: 'info' },
  { name: 'Candidate D', score: null, status: 'Missing must-have', tone: 'warning' },
]

const SAMPLE_TRANSCRIPT = [
  { speaker: 'You', text: 'How would you scale a FastAPI service?' },
  { speaker: 'Candidate', text: 'Several workers behind a load balancer, with caching…' },
  { speaker: 'You', text: 'Have you run it on Kubernetes?' },
]

const SAMPLE_DIMENSIONS = [
  { label: 'Technical', value: 86 },
  { label: 'Communication', value: 79 },
  { label: 'Problem-solving', value: 72 },
  { label: 'Alignment', value: 81 },
]

const TOUR_TABS = ['1 · Screening', '2 · Live interview', '3 · Report']

function Eyebrow({ children }) {
  return (
    <span className="text-[13px] font-bold uppercase tracking-widest text-brand">{children}</span>
  )
}

function delay(seconds) {
  return { animationDelay: `${seconds}s` }
}

function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-[#eef3fc] bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-5 px-6 py-4">
        <Logo />
        <nav aria-label="Main" className="flex flex-wrap gap-8 text-[15px] font-semibold text-navy">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="hover:text-brand">
              {link.label}
            </a>
          ))}
        </nav>
        <Button to="/login">Sign in</Button>
      </div>
    </header>
  )
}

function ScoreRing({ value, label }) {
  // 302 is the length of the circle, so the offset leaves the score's share.
  const offset = Math.round(302 * (1 - value / 100))
  return (
    <div className="relative size-26">
      <svg viewBox="0 0 104 104" aria-hidden="true" className="size-26">
        <circle cx="52" cy="52" r="48" fill="none" stroke="#eaf1ff" strokeWidth="8" />
        <circle
          cx="52"
          cy="52"
          r="48"
          fill="none"
          stroke="#1557e0"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray="302"
          strokeDashoffset={offset}
          transform="rotate(-90 52 52)"
          className="animate-ring-fill"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-3xl font-extrabold leading-none text-navy">{value}</span>
        <span className="text-[11px] font-bold text-brand">{label}</span>
      </div>
    </div>
  )
}

function SampleCandidateCard() {
  return (
    <div
      className="relative z-1 flex w-full max-w-105 animate-rise-up flex-col gap-4 rounded-[28px] border border-line bg-white p-7 shadow-[0_34px_70px_rgb(11_31_75/0.14)]"
      style={delay(0.2)}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest">Sample candidate</p>
          <p className="font-display text-[21px] font-extrabold text-navy">Candidate A</p>
        </div>
        <ScoreRing value={86} label="Strong fit" />
      </div>
      {SAMPLE_SCORES.map((score, index) => (
        <div key={score.label} className="flex flex-col gap-1.5">
          <div className="flex justify-between text-sm">
            <span>{score.label}</span>
            <span className="font-bold text-navy">{score.value}</span>
          </div>
          <div className="h-2 rounded-full bg-tint">
            <div
              className={`h-2 animate-bar-grow rounded-full ${
                score.violet
                  ? 'bg-linear-to-r from-[#7c3aed] to-[#a78bfa]'
                  : 'bg-linear-to-r from-brand to-[#4c82f2]'
              }`}
              style={{ width: `${score.value}%`, ...delay(0.6 + index * 0.15) }}
            />
          </div>
        </div>
      ))}
      <div
        className="flex animate-rise-up flex-col gap-1.5 rounded-2xl bg-mist p-4"
        style={delay(1.3)}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-bold text-navy">Python web development</span>
          <StatusChip tone="success">Met</StatusChip>
        </div>
        <p className="text-sm leading-relaxed text-navy">
          “Built REST services in{' '}
          <mark className="rounded bg-[#dce8ff] px-1 text-navy">Django</mark>
          …” <span className="text-body">· CV, work history</span>
        </p>
      </div>
    </div>
  )
}

// Small cards that float around the sample card in the hero.
function FloatingNote({ className, style, iconClass, icon: Icon, small, text }) {
  return (
    <div
      aria-hidden="true"
      className={`absolute z-2 hidden animate-float sm:flex items-center gap-2.5 rounded-2xl border border-line bg-white px-4 py-3 shadow-[0_16px_34px_rgb(11_31_75/0.12)] ${className}`}
      style={style}
    >
      <span className={`flex size-8 items-center justify-center rounded-[10px] ${iconClass}`}>
        <Icon className="size-4.5" strokeWidth={2.4} />
      </span>
      <span className="flex flex-col">
        <span className="text-xs">{small}</span>
        <span className="text-sm font-bold text-navy">{text}</span>
      </span>
    </div>
  )
}

function Hero() {
  return (
    <section className="relative mx-4 mt-4 overflow-hidden rounded-[36px] bg-mist md:mx-6">
      {/* Soft light drifting behind the content. */}
      <div
        aria-hidden="true"
        className="absolute -right-30 -top-45 size-140 animate-glow-drift rounded-full bg-[radial-gradient(circle,rgb(21_87_224/0.22)_0%,transparent_68%)]"
      />
      <div
        aria-hidden="true"
        className="absolute -bottom-55 -left-40 size-130 animate-glow-drift-back rounded-full bg-[radial-gradient(circle,rgb(124_58_237/0.16)_0%,transparent_68%)]"
      />
      <div
        aria-hidden="true"
        className="absolute left-[44%] top-[30%] size-90 animate-glow-drift rounded-full bg-[radial-gradient(circle,rgb(5_150_105/0.12)_0%,transparent_68%)] [animation-duration:18s]"
      />

      <div className="relative mx-auto flex max-w-6xl flex-wrap items-center gap-16 px-6 py-16 md:px-8 md:py-22">
        <div className="flex flex-1 basis-115 flex-col items-start gap-6.5">
          <span className="inline-flex animate-rise-up items-center gap-2.5 rounded-full border border-line bg-white py-2 pl-3 pr-4 text-[13px] font-semibold text-brand-dark">
            <span
              className="size-2.5 animate-pulse-ring rounded-full bg-brand"
              aria-hidden="true"
            />
            AI-powered recruitment and interview intelligence
          </span>
          <h1
            className="animate-rise-up text-4xl font-extrabold leading-[1.06] tracking-tight md:text-[62px]"
            style={delay(0.08)}
          >
            Hire with clarity. Decide with{' '}
            <span className="animate-marker-sweep text-brand">evidence</span>.
          </h1>
          <p className="max-w-xl animate-rise-up text-[19px] leading-relaxed" style={delay(0.16)}>
            HireLucent screens CVs, runs the live interview and turns both into one assessment where
            every score points back to what the candidate wrote or said.
          </p>
          <div className="flex animate-rise-up flex-wrap items-center gap-4.5" style={delay(0.24)}>
            <Button
              to="/login"
              className="min-h-14 animate-shine px-8 text-base shadow-[0_12px_26px_rgb(21_87_224/0.3)]"
            >
              Sign in to your workspace <ArrowRight className="size-4.5" aria-hidden="true" />
            </Button>
            <a
              href="#how"
              className="inline-flex min-h-14 items-center rounded-full border border-line bg-white px-6 font-bold text-navy hover:text-brand"
            >
              See how it works
            </a>
          </div>
          <ul
            className="flex animate-rise-up flex-wrap gap-5.5 text-sm font-semibold text-navy"
            style={delay(0.32)}
          >
            {HERO_POINTS.map((point) => (
              <li key={point} className="flex items-center gap-2">
                <Check className="size-4.5 text-[#059669]" strokeWidth={2.6} aria-hidden="true" />
                {point}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative flex flex-1 basis-110 justify-center px-2.5 py-8">
          <SampleCandidateCard />
          <FloatingNote
            className="-left-1.5 top-1"
            icon={Check}
            iconClass="bg-success-soft text-[#059669]"
            small="Requirement R2"
            text="Evidence found in CV"
          />
          <FloatingNote
            className="-right-3.5 bottom-8"
            style={delay(1.4)}
            icon={Clock}
            iconClass="bg-[#ffedd5] text-[#ea580c]"
            small="Report draft"
            text="Waiting for your approval"
          />
          <div
            aria-hidden="true"
            className="absolute -top-1.5 right-1.5 z-2 hidden animate-float sm:flex items-center gap-2.5 rounded-[14px] bg-navy px-3.5 py-2.5 shadow-[0_16px_34px_rgb(11_31_75/0.22)]"
            style={delay(0.7)}
          >
            <span className="text-[13px] font-bold text-white">Live transcript</span>
            <span className="flex gap-1">
              {[0, 0.2, 0.4].map((start) => (
                <span
                  key={start}
                  className="size-1.5 animate-dot rounded-full bg-[#a9c8ff]"
                  style={delay(start)}
                />
              ))}
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}

// The three screens of the product tour. Each one shows for 4 s of a 12 s
// cycle; without motion only the first one is shown.
function TourScreening() {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <span className="font-display text-lg font-extrabold text-navy">
          Final ranking · Backend Developer
        </span>
        <span className="text-[13px] font-bold text-[#6d28d9]">Ranked with evidence</span>
      </div>
      {SAMPLE_RANKING.map((row, index) => (
        <div
          key={row.name}
          className="flex items-center gap-3.5 rounded-2xl border border-[#eef3fc] bg-white px-4 py-3"
        >
          <span className="w-4.5 font-display font-extrabold text-[#7c3aed]">{index + 1}</span>
          <span className="flex-1 font-bold text-navy">{row.name}</span>
          <StatusChip tone={row.tone}>{row.status}</StatusChip>
          <span className="hidden h-2 w-40 rounded-full bg-[#ede9fe] sm:block">
            <span
              className="block h-2 rounded-full bg-[#7c3aed]"
              style={{ width: `${row.score ?? 0}%` }}
            />
          </span>
          <span className="w-8 text-right font-extrabold text-navy">{row.score ?? '–'}</span>
        </div>
      ))}
    </div>
  )
}

function TourInterview() {
  return (
    <div className="flex h-full flex-wrap gap-4.5">
      <div className="relative flex min-h-50 flex-[1.2_1_260px] items-end justify-center overflow-hidden rounded-[18px] bg-linear-160 from-[#1e3a8a] to-navy">
        <svg viewBox="0 0 170 170" aria-hidden="true" className="w-47">
          <circle cx="85" cy="64" r="34" fill="#93c5fd" />
          <path d="M20 170c4-40 32-62 65-62s61 22 65 62z" fill="#93c5fd" />
        </svg>
        <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-navy/70 px-2.5 py-1 text-xs font-bold text-white">
          <span className="size-2 rounded-full bg-[#f87171]" aria-hidden="true" />
          12:48
        </span>
      </div>
      <div className="flex flex-[1_1_240px] flex-col gap-2.5 rounded-[18px] bg-mist p-4">
        <span className="text-xs font-bold text-[#047857]">Live transcript · listening</span>
        {SAMPLE_TRANSCRIPT.map((line) => (
          <p key={line.text} className="flex gap-2.5 text-sm">
            <span
              className={`w-18 shrink-0 font-bold ${
                line.speaker === 'You' ? 'text-brand' : 'text-[#047857]'
              }`}
            >
              {line.speaker}
            </span>
            <span className="text-navy">{line.text}</span>
          </p>
        ))}
        <span className="mt-auto self-start rounded-full bg-[#ede9fe] px-3 py-1 text-xs font-bold text-[#6d28d9]">
          Area to probe: Kubernetes
        </span>
      </div>
    </div>
  )
}

function TourReport() {
  return (
    <div className="flex h-full flex-wrap gap-5.5">
      <div className="flex flex-[0_0_210px] flex-col items-center justify-center gap-2.5 rounded-[18px] bg-[#fff7ed] p-4">
        <div className="relative size-30">
          <svg viewBox="0 0 92 92" aria-hidden="true" className="size-30">
            <circle cx="46" cy="46" r="40" fill="none" stroke="#ffedd5" strokeWidth="8" />
            <circle
              cx="46"
              cy="46"
              r="40"
              fill="none"
              stroke="#ea580c"
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray="251"
              strokeDashoffset="45"
              transform="rotate(-90 46 46)"
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center font-display text-3xl font-extrabold text-navy">
            82
          </span>
        </div>
        <span className="font-bold text-navy">Overall · Strong fit</span>
        <span className="rounded-full bg-[#ffedd5] px-3 py-1 text-xs font-bold text-[#c2410c]">
          Draft · waiting for you
        </span>
      </div>
      <div className="flex flex-[1_1_280px] flex-col gap-2.5">
        <span className="font-display text-lg font-extrabold text-navy">Assessment report</span>
        {SAMPLE_DIMENSIONS.map((dimension) => (
          <div key={dimension.label} className="flex items-center gap-2.5 text-[13px]">
            <span className="w-30">{dimension.label}</span>
            <span className="h-2 flex-1 rounded-full bg-[#ffedd5]">
              <span
                className="block h-2 rounded-full bg-[#ea580c]"
                style={{ width: `${dimension.value}%` }}
              />
            </span>
          </div>
        ))}
        <p className="rounded-2xl bg-mist px-3.5 py-3 text-[13px] text-navy">
          <b>Strength</b> · Explained caching and load balancing with a concrete example.{' '}
          <span className="text-body">“Several workers behind…” · 12:31</span>
        </p>
      </div>
    </div>
  )
}

const TOUR_SCREENS = [TourScreening, TourInterview, TourReport]

function ProductTour() {
  return (
    <section
      aria-label="Product tour"
      className="mx-auto flex max-w-6xl flex-col items-center gap-6.5 px-6 pb-2.5 pt-18"
    >
      <div className="flex flex-col items-center gap-2.5 text-center">
        <Eyebrow>See it in action</Eyebrow>
        <h2 className="text-3xl font-extrabold leading-tight tracking-tight md:text-[42px]">
          From a pile of CVs to a clear decision
        </h2>
      </div>
      <div className="w-full max-w-250 animate-rise-up overflow-hidden rounded-[26px] border border-line bg-white shadow-[0_36px_80px_rgb(11_31_75/0.14)]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-mist px-4.5 py-3">
          <span className="flex gap-1.75" aria-hidden="true">
            <span className="size-2.75 rounded-full bg-[#f87171]" />
            <span className="size-2.75 rounded-full bg-[#fbbf24]" />
            <span className="size-2.75 rounded-full bg-[#34d399]" />
          </span>
          <span className="flex gap-1.5 rounded-[14px] bg-tint p-1" aria-hidden="true">
            {TOUR_TABS.map((tab, index) => (
              <span
                key={tab}
                className="relative animate-tour-tab rounded-xl px-4.5 py-2.5 text-sm font-bold text-body"
                style={delay(index * 4)}
              >
                {tab}
                <span
                  className="absolute inset-x-3.5 bottom-1 h-0.75 animate-tour-progress rounded-full bg-brand"
                  style={delay(index * 4)}
                />
              </span>
            ))}
          </span>
          <span className="w-12" aria-hidden="true" />
        </div>
        <div className="relative h-90 bg-[#fbfcff] max-sm:h-auto">
          {TOUR_SCREENS.map((Screen, index) => (
            <div
              key={TOUR_TABS[index]}
              className={`absolute inset-0 animate-tour-panel p-6.5 opacity-0 motion-reduce:opacity-100 max-sm:relative max-sm:animate-none max-sm:opacity-100 ${
                index > 0 ? 'motion-reduce:hidden max-sm:hidden' : ''
              }`}
              style={delay(index * 4)}
            >
              <Screen />
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function HowItWorks() {
  return (
    <section
      id="how"
      className="mx-auto flex max-w-6xl scroll-mt-24 flex-col gap-11 px-6 pb-10 pt-21"
    >
      <div className="flex max-w-2xl flex-col gap-3">
        <Eyebrow>How it works</Eyebrow>
        <h2 className="text-3xl font-extrabold leading-tight tracking-tight md:text-[42px]">
          One workflow, from job post to hiring decision
        </h2>
      </div>
      <div className="relative">
        <div
          aria-hidden="true"
          className="absolute inset-x-[4%] top-7.75 hidden h-1 animate-draw-x rounded-full bg-linear-to-r from-[#2563eb] via-[#7c3aed] via-60% to-[#ea580c] lg:block"
        />
        <ol className="relative grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <li
              key={step.title}
              className="hover-lift flex animate-rise-up flex-col gap-3.5 rounded-3xl border border-line bg-white px-6 pb-6.5 shadow-card"
              style={delay(0.2 + index * 0.15)}
            >
              <span
                className="mt-2 flex size-12 items-center justify-center rounded-2xl font-display text-xl font-extrabold text-white"
                style={{ backgroundColor: step.color, boxShadow: `0 10px 20px ${step.color}4d` }}
              >
                {index + 1}
              </span>
              <span className={`text-xs font-bold uppercase tracking-widest ${step.label}`}>
                {step.stage}
              </span>
              <h3 className="text-xl font-bold">{step.title}</h3>
              <p className="text-[15px] leading-relaxed">{step.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

function Features() {
  return (
    <section
      id="features"
      className="mx-auto flex max-w-6xl scroll-mt-24 flex-col gap-10 px-6 pb-22 pt-15"
    >
      <div className="flex max-w-2xl flex-col gap-3">
        <Eyebrow>Features</Eyebrow>
        <h2 className="text-3xl font-extrabold leading-tight tracking-tight md:text-[42px]">
          Intelligence at every step, with you in control
        </h2>
      </div>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(({ icon: Icon, tint, title, text }) => (
          <div
            key={title}
            className="hover-lift flex flex-col gap-3 rounded-3xl border border-line bg-white p-7"
          >
            <span className={`flex size-12 items-center justify-center rounded-[14px] ${tint}`}>
              <Icon className="size-6" aria-hidden="true" />
            </span>
            <h3 className="text-[19px] font-bold">{title}</h3>
            <p className="text-[15px] leading-relaxed">{text}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function Principles() {
  return (
    <section
      id="principles"
      className="relative mx-4 scroll-mt-24 overflow-hidden rounded-[36px] bg-linear-135 from-royal to-brand md:mx-6"
    >
      <div
        aria-hidden="true"
        className="absolute -right-25 -top-40 size-115 animate-glow-drift-back rounded-full bg-[radial-gradient(circle,rgb(169_200_255/0.35)_0%,transparent_68%)]"
      />
      <div className="relative mx-auto flex max-w-6xl flex-col gap-10 px-6 py-18 md:px-10">
        <h2 className="text-3xl font-extrabold tracking-tight text-white md:text-[42px]">
          AI assists. People decide.
        </h2>
        <div className="grid gap-8 md:grid-cols-3">
          {PRINCIPLES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="flex flex-col gap-3">
              <span className="flex size-11.5 items-center justify-center rounded-[14px] bg-white/15">
                <Icon className="size-5.5 text-white" aria-hidden="true" />
              </span>
              <h3 className="text-xl font-bold text-white">{title}</h3>
              <p className="text-[15px] leading-relaxed text-[#d5e2ff]">{text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function CallToAction() {
  return (
    <section className="mx-auto flex max-w-6xl flex-col items-center gap-5.5 px-6 py-20 text-center">
      <h2 className="text-3xl font-extrabold tracking-tight md:text-[38px]">
        Ready to hire with evidence?
      </h2>
      <p className="max-w-xl text-lg leading-relaxed">
        Sign in to create your first job and let HireLucent do the groundwork while you make the
        decisions.
      </p>
      <Button to="/login" className="min-h-14 px-8 text-base">
        Sign in to your workspace
      </Button>
    </section>
  )
}

export default function LandingPage() {
  return (
    <div className="overflow-x-clip">
      <Header />
      <main>
        <Hero />
        <ProductTour />
        <HowItWorks />
        <Features />
        <Principles />
        <CallToAction />
      </main>
      <footer className="mx-auto flex max-w-6xl flex-wrap justify-between gap-4 border-t border-[#eef3fc] px-6 pb-10 pt-6 text-sm">
        <span>HireLucent · Bringing clarity and intelligence to candidate evaluation.</span>
        <span>BJIT Academy AI Trainee final project</span>
      </footer>
    </div>
  )
}
