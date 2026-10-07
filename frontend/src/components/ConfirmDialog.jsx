import { useEffect } from 'react'
import Button from './Button.jsx'

// Asks the interviewer to confirm an action that cannot be undone.
export default function ConfirmDialog({
  title,
  confirmLabel,
  isBusy = false,
  error = '',
  onConfirm,
  onCancel,
  children,
}) {
  useEffect(() => {
    function handleKey(event) {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onCancel])

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-navy/30 p-4"
      onClick={onCancel}
    >
      <section
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        className="flex w-full max-w-md animate-rise-in flex-col gap-4 rounded-card bg-white p-6 shadow-card"
      >
        <h2 className="text-xl font-extrabold tracking-tight">{title}</h2>
        <div className="flex flex-col gap-2 text-[15px] leading-relaxed">{children}</div>
        {error && (
          <p role="alert" className="text-sm font-semibold text-danger">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <Button variant="soft" onClick={onCancel} disabled={isBusy}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={isBusy}>
            {isBusy ? 'Deleting…' : confirmLabel}
          </Button>
        </div>
      </section>
    </div>
  )
}
