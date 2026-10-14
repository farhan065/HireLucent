import { useEffect } from 'react'
import Button from './Button.jsx'

// Asks the interviewer to confirm an action that cannot be undone, or one
// that changes many candidates at once. "icon" and "lead" are shown beside
// the title, the rest below it. "confirmDisabled" holds the action back, for
// example while a message is empty.
export default function ConfirmDialog({
  title,
  confirmLabel,
  cancelLabel = 'Cancel',
  icon: Icon,
  lead,
  busyLabel = 'Deleting…',
  confirmVariant = 'danger',
  isBusy = false,
  confirmDisabled = false,
  isWide = false,
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
        className={`flex max-h-[calc(100dvh-2rem)] w-full animate-rise-in flex-col gap-4 overflow-y-auto rounded-card bg-white p-6 shadow-card ${
          Icon || isWide ? 'max-w-xl' : 'max-w-md'
        }`}
      >
        <div className="flex items-start gap-3.5">
          {Icon && (
            <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-amber-soft text-amber">
              <Icon className="size-5.5" aria-hidden="true" />
            </span>
          )}
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <h2 className="text-xl font-extrabold tracking-tight">{title}</h2>
            {lead && <p className="text-[15px] leading-relaxed">{lead}</p>}
          </div>
        </div>
        <div className="flex flex-col gap-2 text-[15px] leading-relaxed">{children}</div>
        {error && (
          <p role="alert" className="text-sm font-semibold text-danger">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <Button variant="soft" onClick={onCancel} disabled={isBusy}>
            {cancelLabel}
          </Button>
          <Button
            variant={confirmVariant}
            onClick={onConfirm}
            disabled={isBusy || confirmDisabled}
          >
            {isBusy ? busyLabel : confirmLabel}
          </Button>
        </div>
      </section>
    </div>
  )
}
