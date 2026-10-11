import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { apiRequest } from '../../lib/api.js'
import { totalCandidates } from '../../lib/jobs.js'
import ConfirmDialog from '../ConfirmDialog.jsx'

// Deletes a job, or a draft that has not saved a job yet, after the
// interviewer confirms. With a label it is a text button, without one an icon.
export default function DeleteJobButton({ job, conversation, label, onDeleted }) {
  const [isOpen, setIsOpen] = useState(false)
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState('')
  const title = job?.title ?? conversation.title
  const applicants = totalCandidates(job)

  async function handleConfirm() {
    setIsBusy(true)
    setError('')
    try {
      const path = job ? `/jobs/${job.id}` : `/chat/conversations/${conversation.thread_id}`
      await apiRequest(path, { method: 'DELETE' })
      onDeleted()
    } catch (deleteError) {
      setError(deleteError.message)
      setIsBusy(false)
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label={label ? undefined : `Delete ${title}`}
        onClick={() => setIsOpen(true)}
        className={
          label
            ? 'flex min-h-10 items-center gap-1.5 text-[15px] font-semibold text-danger hover:opacity-80'
            : 'flex size-10 items-center justify-center rounded-xl text-body hover:bg-danger-soft hover:text-danger'
        }
      >
        <Trash2 className="size-4.5" aria-hidden="true" />
        {label}
      </button>

      {isOpen && (
        <ConfirmDialog
          title={`Delete ${title}?`}
          confirmLabel="Delete"
          isBusy={isBusy}
          error={error}
          onConfirm={handleConfirm}
          onCancel={() => setIsOpen(false)}
        >
          {job ? (
            <>
              <p>
                This removes the job
                {applicants > 0 &&
                  `, its ${applicants} ${applicants === 1 ? 'applicant' : 'applicants'}, their CV files and screening results`}
                , and its conversation with the AI Agent.
              </p>
              {job.post_url && (
                <p>The public job post and the application form are not removed.</p>
              )}
            </>
          ) : (
            <p>This removes the conversation. No job was saved from it yet.</p>
          )}
          <p className="font-semibold text-navy">This cannot be undone.</p>
        </ConfirmDialog>
      )}
    </>
  )
}
