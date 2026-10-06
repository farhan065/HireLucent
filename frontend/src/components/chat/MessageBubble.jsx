import Markdown from './Markdown.jsx'

// The small HireLucent mark shown beside everything the assistant says.
export function AssistantMark() {
  return (
    <span
      aria-hidden="true"
      className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-brand"
    >
      <img src="/favicon.svg" alt="" className="size-6" />
    </span>
  )
}

// A row with the assistant's mark on the left and its content beside it.
export function AssistantRow({ children }) {
  return (
    <div className="flex animate-rise-in items-start gap-2.5">
      <AssistantMark />
      <div className="flex min-w-0 flex-1 flex-col gap-2.5">{children}</div>
    </div>
  )
}

export function UserBubble({ text }) {
  return (
    <p className="max-w-[76%] animate-rise-in self-end whitespace-pre-wrap rounded-[18px] rounded-br-sm bg-brand px-4 py-3 text-[15px] leading-normal text-white">
      {text}
    </p>
  )
}

export function AssistantText({ text, isWriting = false }) {
  return (
    <div className="pt-1 text-[15px] text-navy">
      <Markdown>{text}</Markdown>
      {isWriting && <WritingCaret />}
    </div>
  )
}

export function NoteLine({ text }) {
  return (
    <p className="animate-rise-in self-center rounded-full bg-tint px-3.5 py-1 text-[13px] text-brand-dark">
      {text}
    </p>
  )
}

export function WritingCaret() {
  return (
    <span
      aria-hidden="true"
      className="ml-0.5 inline-block h-4 w-0.5 animate-blink bg-brand align-middle"
    />
  )
}

export function ThinkingDots() {
  return (
    <span role="status" aria-label="The assistant is working" className="flex gap-1 pt-3">
      {[0, 1, 2].map((dot) => (
        <span
          key={dot}
          className="size-1.5 animate-dot rounded-full bg-brand"
          style={{ animationDelay: `${dot * 0.2}s` }}
        />
      ))}
    </span>
  )
}
