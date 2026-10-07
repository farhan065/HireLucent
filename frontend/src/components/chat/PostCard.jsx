import { ExternalLink } from 'lucide-react'
import { useState } from 'react'
import Button from '../Button.jsx'
import StatusChip from '../StatusChip.jsx'
import Markdown from './Markdown.jsx'

const STATUS_CHIPS = {
  waiting: { tone: 'info', label: 'Needs your approval' },
  approved: { tone: 'success', label: 'Approved by you' },
  changed: { tone: 'neutral', label: 'Changed' },
}

const FIELD_CLASS =
  'w-full rounded-xl border-[1.5px] border-line px-3 py-2.5 text-[15px] font-normal text-navy'

function Row({ label, children }) {
  return (
    <div className="flex gap-3 text-sm">
      <span className="w-24 shrink-0">{label}</span>
      <span className="min-w-0 break-all text-navy">{children}</span>
    </div>
  )
}

// The form shown when the interviewer changes the post title or the form.
function PostEditor({ post, onSave, onCancel }) {
  const [title, setTitle] = useState(post.title)
  const [formLink, setFormLink] = useState(post.form_link)
  const isValid = title.trim().length >= 3 && formLink.trim().length >= 10

  return (
    <div className="flex flex-col gap-3 px-4 py-3.5">
      <label className="flex flex-col gap-1.5 text-sm font-semibold text-navy">
        Post title
        <input
          value={title}
          maxLength={255}
          onChange={(event) => setTitle(event.target.value)}
          className={FIELD_CLASS}
        />
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-semibold text-navy">
        Google Form link
        <input
          value={formLink}
          maxLength={500}
          onChange={(event) => setFormLink(event.target.value)}
          className={FIELD_CLASS}
        />
      </label>
      <p className="text-[13px]">
        Use the form&apos;s editing address, copied from the browser bar in Google Forms. The
        form is checked again before the post is shown.
      </p>
      <div className="flex flex-wrap justify-end gap-2.5">
        <Button variant="soft" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          disabled={!isValid}
          onClick={() => onSave({ title: title.trim(), form_link: formLink.trim() })}
        >
          Check and show again
        </Button>
      </div>
    </div>
  )
}

// The job post exactly as it will be published.
function PostPreview({ post, isOpen }) {
  return (
    <div className="rounded-2xl border border-line bg-mist/40 px-4.5 py-4 text-[15px]">
      <h3 className="text-xl font-extrabold tracking-tight">{post.title}</h3>
      <p className="mt-1 text-[13px]">
        Job code: <strong className="text-navy">{post.job_code}</strong>
      </p>
      <div className={isOpen ? '' : 'line-clamp-4'}>
        <Markdown>{post.description}</Markdown>
      </div>
      {isOpen && (
        <div className="mt-4 flex flex-col items-start gap-2 border-t border-dashed border-line pt-3.5">
          <strong className="font-display text-navy">How to apply</strong>
          <p>
            Submit your CV through the application form. Job code:{' '}
            <strong className="text-navy">{post.job_code}</strong>
          </p>
          <a
            href={post.form_url}
            target="_blank"
            rel="noreferrer"
            className="font-semibold text-brand underline hover:text-brand-dark"
          >
            Apply now
          </a>
        </div>
      )}
    </div>
  )
}

// The job post waiting to be published. Nothing becomes public until the
// interviewer approves this card.
export default function PostCard({ item, canAct, onPublish, onEdit }) {
  const post = item.arguments
  const isWaiting = item.status === 'waiting'
  const [isOpen, setIsOpen] = useState(isWaiting)
  const [isEditing, setIsEditing] = useState(false)
  const chip = STATUS_CHIPS[item.status] ?? STATUS_CHIPS.changed

  function handleSave(changes) {
    setIsEditing(false)
    onEdit(changes)
  }

  return (
    <article
      className={`overflow-hidden rounded-2xl border bg-white ${
        isWaiting ? 'border-brand shadow-card' : 'border-line'
      } ${item.status === 'changed' ? 'opacity-70' : ''}`}
    >
      <header className="flex flex-wrap items-center justify-between gap-2.5 bg-mist px-4 py-3">
        <span className="font-display text-[15px] font-bold text-navy">
          {isWaiting ? 'Your decision: publish this job post' : 'Job post'}
        </span>
        <StatusChip tone={chip.tone}>{isEditing ? 'Editing' : chip.label}</StatusChip>
      </header>

      {isEditing ? (
        <PostEditor post={post} onSave={handleSave} onCancel={() => setIsEditing(false)} />
      ) : (
        <div className="flex flex-col gap-3 px-4 py-3.5">
          <div className="flex flex-col gap-1.5">
            <Row label="Publishes to">Your public careers blog</Row>
            <Row label="Apply form">
              <a
                href={post.form_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 font-semibold text-brand hover:text-brand-dark"
              >
                {post.form_title}
                <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
              </a>
            </Row>
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest">Post preview</p>
          <PostPreview post={post} isOpen={isOpen} />
          <button
            type="button"
            onClick={() => setIsOpen((open) => !open)}
            className="self-start text-sm font-semibold text-brand hover:text-brand-dark"
          >
            {isOpen ? 'Show less' : 'Show the full post'}
          </button>
        </div>
      )}

      {isWaiting && canAct && !isEditing && (
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3">
          <span className="text-sm">Nothing is public until you approve.</span>
          <div className="flex flex-wrap gap-2.5">
            <Button variant="outline" onClick={() => setIsEditing(true)}>
              Edit
            </Button>
            <Button onClick={onPublish}>Approve and publish</Button>
          </div>
        </footer>
      )}
    </article>
  )
}
