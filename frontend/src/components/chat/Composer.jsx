import { ArrowUp } from 'lucide-react'
import { useState } from 'react'

// Replies offered for each stage, so common answers take one click.
const SUGGESTIONS = {
  describing: [
    'A backend engineer with Python and FastAPI, 2 years of experience',
    'A UI designer with Figma experience',
    'A data analyst who knows SQL and Python',
  ],
  reviewing_description: ['Make it a senior role', 'Shorten it', 'Add a hybrid work arrangement'],
  confirming_requirements: [
    'Looks good, save it',
    'Give experience more weight',
    'Make all technical skills must-haves',
  ],
  saved: [],
  confirming_post: ['Looks good, publish it'],
  published: [],
}

const PLACEHOLDERS = {
  describing: 'Describe the role you are hiring for…',
  saved: 'Paste the Google Form link…',
  published: 'Message the assistant…',
}

// The message box with suggested replies above it. "inputRef" lets the
// page put the cursor in the box, for example after "Request changes".
export default function Composer({ stage, isDisabled, onSend, inputRef }) {
  const [text, setText] = useState('')

  function submit(message) {
    const trimmed = message.trim()
    if (!trimmed || isDisabled) return
    onSend(trimmed)
    setText('')
  }

  function handleKeyDown(event) {
    // Enter sends. Shift+Enter starts a new line.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit(text)
    }
  }

  return (
    <div className="flex flex-col gap-2.5">
      {SUGGESTIONS[stage].length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px]">Suggested replies</span>
          {SUGGESTIONS[stage].map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              disabled={isDisabled}
              onClick={() => submit(suggestion)}
              className="min-h-9 rounded-full border-[1.5px] border-line bg-white px-3.5 text-sm font-semibold text-brand-dark hover:border-brand disabled:opacity-50"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-end gap-2.5 rounded-[18px] border-[1.5px] border-line bg-white py-2 pl-4 pr-2 shadow-card focus-within:border-brand">
        <textarea
          ref={inputRef}
          aria-label="Message the AI Agent"
          rows={1}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            PLACEHOLDERS[stage] ?? 'Tell the assistant what to change…'
          }
          className="max-h-40 min-h-11 flex-1 resize-none bg-transparent py-2.5 text-[15px] text-navy outline-none placeholder:text-body/60"
        />
        <button
          type="button"
          aria-label="Send"
          disabled={isDisabled || !text.trim()}
          onClick={() => submit(text)}
          className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-brand text-white hover:bg-brand-dark disabled:bg-line disabled:text-body"
        >
          <ArrowUp className="size-5" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
