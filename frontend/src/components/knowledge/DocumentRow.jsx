import { CircleAlert, CircleCheck, FileText, LoaderCircle, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { KIND_BY_VALUE } from '../../lib/knowledge.js'

const STATUSES = {
  ready: { label: 'Ready', tone: 'bg-success-soft text-success', icon: CircleCheck },
  processing: {
    label: 'Processing',
    tone: 'bg-tint text-brand-dark',
    icon: LoaderCircle,
    iconClass: 'motion-safe:animate-spin',
    hint: 'Reading and indexing the text…',
  },
  failed: {
    label: 'Failed',
    tone: 'bg-danger-soft text-danger',
    icon: CircleAlert,
    hint: 'The text could not be read. Delete it and upload it again.',
    hintClass: 'text-danger',
  },
}

const SMALL_BUTTON = 'min-h-9.5 rounded-full px-3.5 text-sm font-semibold'

function formatDate(value) {
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

// One document in the list. The delete button asks for confirmation in the
// row itself before anything is removed.
export default function DocumentRow({ document, onDelete }) {
  const [isConfirming, setIsConfirming] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState('')
  const kind = KIND_BY_VALUE[document.doc_type]
  const status = STATUSES[document.status] ?? STATUSES.failed
  const StatusIcon = status.icon

  async function handleDelete() {
    setIsDeleting(true)
    setError('')
    try {
      await onDelete(document.id)
    } catch (deleteError) {
      setError(deleteError.message)
      setIsDeleting(false)
    }
  }

  return (
    <li
      className={`flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line/60 px-5 py-3.5 ${
        isConfirming ? 'bg-danger-soft/40' : ''
      }`}
    >
      <span className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${kind.tone}`}>
        <FileText className="size-5" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1 basis-56">
        <p className="truncate text-[15px] font-semibold text-navy">{document.filename}</p>
        {(error || status.hint) && (
          <p className={`text-[13px] ${error ? 'text-danger' : (status.hintClass ?? '')}`}>
            {error || status.hint}
          </p>
        )}
      </div>
      <div className="w-30 shrink-0">
        <span className={`rounded-lg px-2.5 py-1 text-[13px] font-semibold ${kind.tone}`}>
          {kind.label}
        </span>
      </div>

      {isConfirming ? (
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-navy">Delete this document?</span>
          <button
            type="button"
            disabled={isDeleting}
            onClick={() => setIsConfirming(false)}
            className={`${SMALL_BUTTON} bg-white text-body ring-1 ring-line hover:bg-mist`}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isDeleting}
            onClick={handleDelete}
            className={`${SMALL_BUTTON} bg-danger text-white hover:opacity-90`}
          >
            {isDeleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      ) : (
        <>
          <div className="flex w-38 shrink-0 flex-wrap gap-1.5">
            {document.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-lg bg-mist px-2 py-0.5 text-xs font-semibold text-body"
              >
                {tag}
              </span>
            ))}
          </div>
          <div className="w-20 shrink-0 text-sm text-navy">
            {document.status === 'ready' ? document.chunk_count : '–'}
            <span className="text-body xl:hidden"> sections</span>
          </div>
          <div className="w-26 shrink-0 text-sm">{formatDate(document.created_at)}</div>
          <div className="w-30 shrink-0">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-semibold ${status.tone}`}
            >
              <StatusIcon className={`size-3.5 ${status.iconClass ?? ''}`} aria-hidden="true" />
              {status.label}
            </span>
          </div>
          <button
            type="button"
            aria-label={`Delete ${document.filename}`}
            onClick={() => setIsConfirming(true)}
            className="flex size-10 shrink-0 items-center justify-center rounded-xl text-body hover:bg-danger-soft hover:text-danger"
          >
            <Trash2 className="size-4.5" aria-hidden="true" />
          </button>
        </>
      )}
    </li>
  )
}
