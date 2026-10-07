import { CircleAlert } from 'lucide-react'
import DocumentList from '../components/knowledge/DocumentList.jsx'
import UploadPanel from '../components/knowledge/UploadPanel.jsx'
import { useDocuments } from '../hooks/useDocuments.js'

function CountChip({ className, children }) {
  return (
    <span className={`rounded-full px-3 py-1 text-[13px] font-semibold ${className}`}>
      {children}
    </span>
  )
}

// Where the interviewer manages the documents the assistant learns from.
export default function KnowledgeBasePage() {
  const { documents, error, upload, remove } = useDocuments()
  const readyCount = documents?.filter((item) => item.status === 'ready').length

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">Knowledge Base</h1>
          <p className="mt-1.5 max-w-2xl text-base">
            Documents the assistant learns from. It uses them to write job descriptions, and
            later to prepare and check interview questions.
          </p>
        </div>
        {documents && (
          <div className="flex gap-2.5">
            <CountChip className="bg-white text-navy">
              {documents.length} {documents.length === 1 ? 'document' : 'documents'}
            </CountChip>
            <CountChip className="bg-success-soft text-success">{readyCount} ready</CountChip>
          </div>
        )}
      </header>

      <UploadPanel onUpload={upload} />

      {error && (
        <p role="alert" className="font-semibold text-danger">
          {error}
        </p>
      )}
      {!documents && !error && <p role="status">Loading…</p>}
      {documents && <DocumentList documents={documents} onDelete={remove} />}

      <p className="flex items-start gap-2.5 rounded-2xl bg-warning-soft px-4 py-3.5 text-sm text-warning">
        <CircleAlert className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
        <span>
          <strong className="font-semibold">Do not upload CVs or personal data here.</strong> Only
          the text is stored for search. The original file is not kept.
        </span>
      </p>
    </div>
  )
}
