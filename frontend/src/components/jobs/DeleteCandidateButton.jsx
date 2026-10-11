import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { apiRequest } from '../../lib/api.js'
import ConfirmDialog from '../ConfirmDialog.jsx'

// Deletes a candidate for good after the interviewer confirms. Not
// available while a fetch or a screening runs for the job.
export default function DeleteCandidateButton({ candidate, isLocked = false, onDeleted }) {
  const [isOpen, setIsOpen] = useState(false)
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState('')

  async function handleConfirm() {
    setIsBusy(true)
    setError('')
    try {
      await apiRequest(`/candidates/${candidate.id}`, { method: 'DELETE' })
      setIsOpen(false)
      onDeleted()
    } catch (deleteError) {
      setError(deleteError.message)
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label={`Delete ${candidate.full_name}`}
        title={isLocked ? 'Available when the run ends' : `Delete ${candidate.full_name}`}
        disabled={isLocked}
        onClick={() => setIsOpen(true)}
        className="flex size-10 shrink-0 items-center justify-center rounded-xl text-body hover:bg-danger-soft hover:text-danger disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-body"
      >
        <Trash2 className="size-4.5" aria-hidden="true" />
      </button>

      {isOpen && (
        <ConfirmDialog
          title={`Delete ${candidate.full_name}?`}
          confirmLabel="Delete"
          isBusy={isBusy}
          error={error}
          onConfirm={handleConfirm}
          onCancel={() => setIsOpen(false)}
        >
          <p>This removes the candidate, their CV file and all their screening results.</p>
          <p>
            Their application is not collected again, even if it is still in the
            application form.
          </p>
          <p className="font-semibold text-navy">This cannot be undone.</p>
        </ConfirmDialog>
      )}
    </>
  )
}
