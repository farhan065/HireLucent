import { useState } from 'react'
import { DOCUMENT_KINDS } from '../../lib/knowledge.js'
import DocumentRow from './DocumentRow.jsx'

const COLUMN_LABEL = 'shrink-0 text-xs font-semibold uppercase tracking-widest'

function FilterTab({ label, count, isActive, onClick }) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onClick}
      className={`min-h-10 rounded-full px-3.5 text-sm font-semibold transition-colors ${
        isActive
          ? 'bg-navy text-white'
          : 'border-[1.5px] border-line bg-white text-body hover:border-brand'
      }`}
    >
      {label} <span className="ml-1 opacity-70">{count}</span>
    </button>
  )
}

// Every uploaded document, with a filter for each kind.
export default function DocumentList({ documents, onDelete }) {
  const [filter, setFilter] = useState('all')
  const shown =
    filter === 'all' ? documents : documents.filter((item) => item.doc_type === filter)

  return (
    <section
      aria-label="Documents"
      className="overflow-hidden rounded-card border border-line bg-white shadow-card"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4.5">
        <h2 className="text-lg font-bold">Documents</h2>
        <div className="flex flex-wrap gap-2">
          <FilterTab
            label="All"
            count={documents.length}
            isActive={filter === 'all'}
            onClick={() => setFilter('all')}
          />
          {DOCUMENT_KINDS.map((kind) => (
            <FilterTab
              key={kind.value}
              label={kind.plural}
              count={documents.filter((item) => item.doc_type === kind.value).length}
              isActive={filter === kind.value}
              onClick={() => setFilter(kind.value)}
            />
          ))}
        </div>
      </div>

      {/* Column names, shown when the row fits on one line. */}
      <div aria-hidden="true" className="hidden items-center gap-4 bg-mist px-5 py-2.5 xl:flex">
        <span className="w-10 shrink-0" />
        <span className={`${COLUMN_LABEL} flex-1 basis-56`}>Document</span>
        <span className={`${COLUMN_LABEL} w-30`}>Kind</span>
        <span className={`${COLUMN_LABEL} w-38`}>Tags</span>
        <span className={`${COLUMN_LABEL} w-20`}>Sections</span>
        <span className={`${COLUMN_LABEL} w-26`}>Added</span>
        <span className={`${COLUMN_LABEL} w-30`}>Status</span>
        <span className="w-10 shrink-0" />
      </div>

      {shown.length === 0 ? (
        <p className="border-t border-line/60 px-5 py-10 text-center">
          {documents.length === 0
            ? 'No documents yet. Upload a job description template to start.'
            : 'No documents of this kind yet.'}
        </p>
      ) : (
        <ul>
          {shown.map((document) => (
            <DocumentRow key={document.id} document={document} onDelete={onDelete} />
          ))}
        </ul>
      )}
    </section>
  )
}
