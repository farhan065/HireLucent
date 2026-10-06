import { X } from 'lucide-react'
import { useEffect } from 'react'

// A panel that slides in from the right over the page. It closes with the
// X button, the Escape key or a click outside it.
export default function SidePanel({ title, onClose, children, footer }) {
  useEffect(() => {
    function handleKey(event) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-navy/30" onClick={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        className="flex h-full w-full max-w-xl animate-slide-in flex-col bg-white shadow-card"
      >
        <header className="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
          <h2 className="text-xl font-extrabold tracking-tight">{title}</h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="flex size-10 items-center justify-center rounded-xl text-body hover:bg-mist"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <footer className="border-t border-line px-6 py-4">{footer}</footer>}
      </section>
    </div>
  )
}
