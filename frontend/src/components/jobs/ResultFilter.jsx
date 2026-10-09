import { ChevronDown } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { RESULT_GROUPS } from '../../lib/results.js'

// The Show dropdown of the Screening tab: pick which results to list. Each
// option shows its count. Works with the mouse and the keyboard.
export default function ResultFilter({ value, counts, onChange }) {
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const rootRef = useRef(null)
  const buttonRef = useRef(null)
  const listRef = useRef(null)
  const id = useId()
  const options = RESULT_GROUPS.filter((group) => !group.isOptional || counts[group.key] > 0)
  const selected = RESULT_GROUPS.find((group) => group.key === value) ?? RESULT_GROUPS[0]
  const isFiltered = value !== 'all'

  // Close when clicking anywhere else, and move focus into the open list.
  useEffect(() => {
    if (!isOpen) return undefined
    listRef.current?.focus()
    function handleClick(event) {
      if (!rootRef.current?.contains(event.target)) setIsOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [isOpen])

  function open() {
    setActiveIndex(Math.max(0, options.findIndex((group) => group.key === value)))
    setIsOpen(true)
  }

  function choose(key) {
    onChange(key)
    setIsOpen(false)
    buttonRef.current?.focus()
  }

  function handleListKey(event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => Math.min(options.length - 1, index + 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => Math.max(0, index - 1))
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      choose(options[activeIndex].key)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setIsOpen(false)
      buttonRef.current?.focus()
    } else if (event.key === 'Tab') {
      setIsOpen(false)
    }
  }

  return (
    <div ref={rootRef} className="relative flex items-center gap-2.5">
      <span id={`${id}-label`} className="text-sm font-semibold">
        Show
      </span>
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-labelledby={`${id}-label ${id}-button`}
        id={`${id}-button`}
        onClick={() => (isOpen ? setIsOpen(false) : open())}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' && !isOpen) {
            event.preventDefault()
            open()
          }
        }}
        className={`flex min-h-11 items-center gap-2.5 rounded-full border-[1.5px] pl-4 pr-3.5 text-[15px] font-semibold text-navy ${
          isFiltered ? 'border-brand bg-tint' : 'border-line bg-white hover:border-brand/40'
        }`}
      >
        {selected.label} ({counts[selected.key]})
        <ChevronDown
          className={`size-4.5 text-body transition-transform ${isOpen ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {isOpen && (
        <ul
          ref={listRef}
          role="listbox"
          tabIndex={-1}
          aria-labelledby={`${id}-label`}
          aria-activedescendant={`${id}-${options[activeIndex]?.key}`}
          onKeyDown={handleListKey}
          className="absolute left-0 top-full z-20 mt-2 w-64 animate-rise-in rounded-2xl border border-line bg-white p-1.5 shadow-card outline-none sm:left-12"
        >
          {options.map((group, index) => {
            const isSelected = group.key === value
            return (
              <li
                key={group.key}
                id={`${id}-${group.key}`}
                role="option"
                aria-selected={isSelected}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => choose(group.key)}
                className={`flex cursor-pointer items-center gap-2.5 rounded-xl px-3 py-2.5 text-[15px] ${
                  isSelected ? 'font-bold text-brand-dark' : 'text-navy'
                } ${index === activeIndex ? 'bg-tint' : ''}`}
              >
                <span className={`size-2.5 shrink-0 rounded-full ${group.dot}`} aria-hidden="true" />
                <span className="flex-1">{group.label}</span>
                <span className="font-semibold text-body">{counts[group.key]}</span>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
