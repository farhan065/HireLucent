import { useState } from 'react'
import { useRequirementsForm } from '../../hooks/useRequirementsForm.js'
import { apiRequest } from '../../lib/api.js'
import Button from '../Button.jsx'
import ConfirmDialog from '../ConfirmDialog.jsx'
import SidePanel from '../SidePanel.jsx'
import { RequirementsFields } from './RequirementsEditor.jsx'

// Changing a saved job's requirements and weights from the job brief. When
// CVs were screened already, saving asks first, because it clears their
// screening results so every candidate is screened with the same rules.
export default function EditProfilePanel({ jobId, subtitle, brief, onSaved, onClose }) {
  const editor = useRequirementsForm({
    requirements: brief.requirements,
    scoring_weights: brief.scoring_weights,
  })
  // The screened count and the new rules, while the reset is being confirmed.
  const [pending, setPending] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')

  async function save(profile) {
    setIsSaving(true)
    setError('')
    try {
      await apiRequest(`/jobs/${jobId}/profile`, { method: 'PUT', body: profile })
      onSaved()
    } catch (saveError) {
      setError(saveError.message)
      setIsSaving(false)
    }
  }

  // Ask the server how many are screened now, not when the panel opened.
  async function handleSave() {
    const profile = editor.value()
    setIsSaving(true)
    setError('')
    try {
      const job = await apiRequest(`/jobs/${jobId}`)
      if (job.screened_count > 0) {
        setPending({ count: job.screened_count, profile })
        setIsSaving(false)
        return
      }
    } catch (loadError) {
      setError(loadError.message)
      setIsSaving(false)
      return
    }
    save(profile)
  }

  function cancelReset() {
    if (isSaving) return
    setPending(null)
    setError('')
  }

  const footer = (
    <div className="flex flex-col gap-2.5">
      {error && !pending && (
        <p role="alert" className="text-sm font-semibold text-danger">
          {error}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-2.5">
        <Button variant="soft" onClick={onClose} disabled={isSaving}>
          Cancel
        </Button>
        <Button disabled={!editor.isValid || isSaving} onClick={handleSave}>
          {isSaving && !pending ? 'Saving…' : 'Save changes'}
        </Button>
      </div>
    </div>
  )

  return (
    <>
      <SidePanel
        title="Edit requirements and weights"
        subtitle={subtitle}
        onClose={pending ? cancelReset : onClose}
        footer={footer}
      >
        <div className="flex flex-col gap-3.5">
          <p className="rounded-xl bg-mist px-3 py-2.5 text-sm leading-normal">
            The job post and description stay as they are. The new rules are used for every CV
            screened from now on.
          </p>
          <RequirementsFields editor={editor} />
        </div>
      </SidePanel>

      {pending && (
        <ConfirmDialog
          title="Change the requirements?"
          confirmLabel="Save and reset screening"
          busyLabel="Saving…"
          confirmVariant="primary"
          isBusy={isSaving}
          error={error}
          onConfirm={() => save(pending.profile)}
          onCancel={cancelReset}
        >
          <p>
            {pending.count} {pending.count === 1 ? 'candidate has' : 'candidates have'} already
            been screened with the current rules. Saving clears their screening results:
            requirement matches, scores, ranks, exclusions and the shortlist.
          </p>
          <p>
            They go back to <strong className="text-navy">ready to screen</strong>. Press{' '}
            <strong className="text-navy">Screen CVs</strong> again to screen them with the new
            rules. Their CVs are not read again.
          </p>
          <p className="rounded-xl bg-mist px-3 py-2.5 text-sm">
            Candidates whose CV could not be read stay as they are.
          </p>
        </ConfirmDialog>
      )}
    </>
  )
}
