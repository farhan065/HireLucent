import { Pencil } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { MAX_MESSAGE, messageProblem, previewEmail } from '../../lib/interviews.js'

// The interviewer's own message in an interview email. Only this paragraph
// can be changed; the server adds the greeting, the time, the Join link and
// the signature around it.

const TEXT = 'whitespace-pre-line text-[13.5px] leading-relaxed text-navy'

// The email as the candidate will see it, with the message highlighted.
export function EmailText({ text, message }) {
  const at = message ? text.indexOf(message) : -1
  if (at < 0) return <p className={TEXT}>{text}</p>
  return (
    <p className={TEXT}>
      {text.slice(0, at)}
      <mark className="rounded bg-warning-soft px-0.5 text-navy">{message}</mark>
      {text.slice(at + message.length)}
    </p>
  )
}

export function EditMessageButton({ onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex min-h-8.5 shrink-0 items-center gap-1.5 rounded-full border-[1.5px] border-brand/25 bg-white px-3 font-display text-[13px] font-bold text-brand hover:border-brand/60"
    >
      <Pencil className="size-3.5" aria-hidden="true" />
      Edit message
    </button>
  )
}

// The message box with its hint and character count. "onDefault" adds a
// "Use the default" link while the message differs from the default.
export function MessageField({ label, value, hint, isDefault = true, onChange, onDefault }) {
  const id = useId()
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={id} className="text-[13.5px] font-semibold text-navy">
          {label}
        </label>
        {onDefault && !isDefault && (
          <button
            type="button"
            onClick={onDefault}
            className="text-[13.5px] font-semibold text-brand hover:text-brand-dark"
          >
            Use the default
          </button>
        )}
      </div>
      <textarea
        id={id}
        rows={4}
        value={value}
        maxLength={MAX_MESSAGE}
        onChange={(event) => onChange(event.target.value)}
        className="w-full resize-y rounded-xl border-[1.5px] border-line px-3 py-2.5 text-[14.5px] leading-normal text-navy focus:border-brand focus:outline-none"
      />
      <div className="flex items-start justify-between gap-3 text-[12.5px]">
        <span>{hint}</span>
        <span className="shrink-0 tabular-nums">
          {value.length} / {MAX_MESSAGE}
        </span>
      </div>
    </div>
  )
}

// The message box and the email preview in the Interviews tab's confirm
// dialogs. "message" is null for the default message. The preview comes
// from the server, so it is exactly what will be sent.
export function DialogMessage({
  jobId,
  kind,
  candidateId,
  candidateName,
  start,
  end,
  label,
  message,
  onChange,
}) {
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const startIso = start.toISOString()
  const endIso = end.toISOString()
  const problem = message == null ? '' : messageProblem(message)

  useEffect(() => {
    if (problem) return undefined
    let isCurrent = true
    // Wait until the interviewer stops typing.
    const timer = setTimeout(
      async () => {
        try {
          const result = await previewEmail(jobId, {
            kind,
            candidate_id: candidateId,
            start: startIso,
            end: endIso,
            message,
          })
          if (isCurrent) {
            setPreview(result)
            setError('')
          }
        } catch (previewError) {
          if (isCurrent) setError(previewError.message)
        }
      },
      message == null ? 0 : 400,
    )
    return () => {
      isCurrent = false
      clearTimeout(timer)
    }
  }, [jobId, kind, candidateId, startIso, endIso, message, problem])

  const defaultMessage = preview?.default_message ?? ''
  const value = message ?? defaultMessage
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-2xl border border-line p-3.5">
        <MessageField
          label={label}
          value={value}
          hint="The time and Join link are added automatically."
          isDefault={message == null || message === defaultMessage}
          onChange={onChange}
          onDefault={() => onChange(null)}
        />
        {(problem || error) && (
          <p role="alert" className="mt-2 text-[13px] font-semibold text-danger">
            {problem || error}
          </p>
        )}
      </div>
      {preview && (
        <div className="flex flex-col gap-1.5 rounded-2xl bg-mist px-3.5 py-3">
          <button
            type="button"
            aria-expanded={isOpen}
            onClick={() => setIsOpen((open) => !open)}
            className="self-start text-[13.5px] font-semibold text-brand hover:text-brand-dark"
          >
            {isOpen ? 'Hide the preview' : 'Show the preview'}
          </button>
          {isOpen && (
            <>
              <span className="text-xs font-semibold uppercase tracking-wider">
                Preview for {candidateName}
              </span>
              <EmailText text={preview.text} message={preview.message} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
