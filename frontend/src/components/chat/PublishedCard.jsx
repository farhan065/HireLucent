import { CircleCheck, Copy, ExternalLink, Globe } from 'lucide-react'
import { useState } from 'react'
import StatusChip from '../StatusChip.jsx'

// Shown once the job post is live, with its public address.
export default function PublishedCard({ url }) {
  const [isCopied, setIsCopied] = useState(false)

  async function copyLink() {
    await navigator.clipboard.writeText(url)
    setIsCopied(true)
    setTimeout(() => setIsCopied(false), 2000)
  }

  return (
    <article className="overflow-hidden rounded-2xl border border-success/30 bg-white">
      <header className="flex flex-wrap items-center justify-between gap-2.5 bg-success-soft px-4 py-3">
        <span className="flex items-center gap-2 font-display text-[15px] font-bold text-success">
          <CircleCheck className="size-4.5" aria-hidden="true" />
          Job post published
        </span>
        <StatusChip tone="success">Live</StatusChip>
      </header>

      <div className="flex flex-col gap-3 px-4 py-3.5">
        <div className="flex items-center gap-2.5 rounded-xl border border-line bg-mist px-3 py-2">
          <Globe className="size-4.5 shrink-0 text-brand" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate text-sm text-navy">{url}</span>
          <button
            type="button"
            onClick={copyLink}
            className="flex min-h-9 shrink-0 items-center gap-1.5 rounded-lg bg-tint px-3 text-[13px] font-semibold text-brand-dark hover:bg-lavender"
          >
            <Copy className="size-3.5" aria-hidden="true" />
            <span role="status">{isCopied ? 'Copied' : 'Copy link'}</span>
          </button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm">
            Candidates can now apply through the form. Next step: fetch the CVs when
            applications arrive.
          </p>
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex min-h-11 items-center gap-2 rounded-full border-[1.5px] border-brand bg-white px-5 font-display text-[15px] font-bold text-brand hover:bg-tint"
          >
            <ExternalLink className="size-4" aria-hidden="true" />
            View post
          </a>
        </div>
      </div>
    </article>
  )
}
