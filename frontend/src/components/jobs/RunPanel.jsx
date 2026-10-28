import { LoaderCircle } from 'lucide-react'
import Button from '../Button.jsx'

// The card at the top of a job tab: one action, and its progress while it
// runs. "task" is the running task of this action, if there is one.
export default function RunPanel({
  title,
  description,
  buttonLabel,
  busyLabel,
  icon: Icon,
  task,
  isDisabled,
  isQuiet = false,
  error,
  onStart,
  children,
}) {
  return (
    <section className="flex flex-col gap-4 rounded-card border border-line bg-white p-6 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-5">
        <div className="flex min-w-0 flex-1 basis-80 flex-col gap-2">
          <h2 className="text-xl font-bold">{title}</h2>
          {!task && <div className="max-w-2xl text-[15px] leading-relaxed">{description}</div>}
        </div>
        <Button
          variant={isQuiet ? 'outline' : 'primary'}
          onClick={onStart}
          disabled={isDisabled || Boolean(task)}
        >
          {task ? (
            <LoaderCircle className="size-4.5 animate-spin" aria-hidden="true" />
          ) : (
            <Icon className="size-4.5" aria-hidden="true" />
          )}
          {task ? busyLabel : buttonLabel}
        </Button>
      </div>

      {task ? (
        <div role="status" className="flex flex-col gap-2.5">
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={task.percent}
            className="h-2 overflow-hidden rounded-full bg-tint"
          >
            <div
              className="h-full rounded-full bg-brand transition-[width] duration-500"
              style={{ width: `${Math.max(task.percent, 4)}%` }}
            />
          </div>
          <p className="text-[15px] font-semibold text-navy">{task.message ?? 'Starting…'}</p>
        </div>
      ) : (
        children
      )}

      {error && (
        <p role="alert" className="text-sm font-semibold text-danger">
          {error}
        </p>
      )}
    </section>
  )
}
