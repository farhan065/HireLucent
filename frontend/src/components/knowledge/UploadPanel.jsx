import { FileText, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { DOCUMENT_KINDS, fileProblem, formatSize, MAX_UPLOAD_MB } from '../../lib/knowledge.js'
import Button from '../Button.jsx'

// The area a file is dropped on or chosen from.
function DropZone({ file, onChoose, onRemove }) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef(null)

  function handleDrop(event) {
    event.preventDefault()
    setIsDragging(false)
    const dropped = event.dataTransfer.files[0]
    if (dropped) onChoose(dropped)
  }

  function handleInput(event) {
    const chosen = event.target.files[0]
    if (chosen) onChoose(chosen)
    // Clear the input so the same file can be chosen again after a removal.
    event.target.value = ''
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={`flex min-h-44 flex-1 basis-72 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed p-5 text-center transition-colors ${
        isDragging ? 'border-brand bg-tint' : 'border-[#a9c8ff] bg-mist'
      }`}
    >
      <span className="flex size-12 items-center justify-center rounded-2xl bg-tint text-brand">
        <Upload className="size-5.5" aria-hidden="true" />
      </span>
      <p className="font-display font-bold text-navy">
        Drop a file here or{' '}
        <button
          type="button"
          onClick={() => inputRef.current.click()}
          className="font-bold text-brand hover:text-brand-dark"
        >
          choose a file
        </button>
      </p>
      <p className="text-[13px]">PDF, DOCX, TXT or Markdown · up to {MAX_UPLOAD_MB} MB</p>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt,.md"
        onChange={handleInput}
        className="sr-only"
        aria-label="Choose a file"
      />
      {file && (
        <p className="mt-1.5 flex max-w-full items-center gap-2 rounded-xl border border-line bg-white px-3 py-1.5 text-sm font-semibold text-navy">
          <FileText className="size-4 shrink-0 text-brand" aria-hidden="true" />
          <span className="truncate">{file.name}</span>
          <span className="shrink-0 font-normal text-body">· {formatSize(file.size)}</span>
          <button
            type="button"
            onClick={onRemove}
            className="shrink-0 text-[13px] font-semibold text-brand hover:text-brand-dark"
          >
            Remove
          </button>
        </p>
      )}
    </div>
  )
}

function KindOption({ kind, isSelected, onSelect }) {
  return (
    <label
      className={`flex flex-1 basis-40 cursor-pointer flex-col gap-2 rounded-2xl border-[1.5px] p-3.5 transition-colors ${
        isSelected ? 'border-brand bg-mist ring-1 ring-brand' : 'border-line bg-white hover:border-brand'
      }`}
    >
      <span className="flex items-center gap-2.5">
        <input
          type="radio"
          name="document-kind"
          checked={isSelected}
          onChange={onSelect}
          className="size-4.5 accent-brand"
        />
        <span className="font-display text-[15px] font-bold text-navy">{kind.label}</span>
      </span>
      <span className="text-[13px] leading-normal">{kind.description}</span>
      <span
        className={`self-start rounded-lg px-2 py-0.5 text-xs font-semibold ${kind.tone}`}
      >
        {kind.usedFor}
      </span>
    </label>
  )
}

// The form for adding one document to the Knowledge Base.
export default function UploadPanel({ onUpload }) {
  const [file, setFile] = useState(null)
  const [kind, setKind] = useState(DOCUMENT_KINDS[0].value)
  const [tags, setTags] = useState('')
  const [error, setError] = useState('')
  const [isUploading, setIsUploading] = useState(false)

  function chooseFile(chosen) {
    const problem = fileProblem(chosen)
    setError(problem)
    setFile(problem ? null : chosen)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setIsUploading(true)
    setError('')
    try {
      await onUpload(file, kind, tags)
      setFile(null)
      setTags('')
    } catch (uploadError) {
      setError(uploadError.message)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-label="Add a document"
      className="flex flex-wrap gap-6 rounded-card border border-line bg-white p-6 shadow-card"
    >
      <DropZone file={file} onChoose={chooseFile} onRemove={() => setFile(null)} />

      <div className="flex flex-2 basis-96 flex-col gap-3.5">
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-3 text-sm font-semibold text-navy">What is this document?</legend>
          <div className="flex flex-wrap gap-3">
            {DOCUMENT_KINDS.map((option) => (
              <KindOption
                key={option.value}
                kind={option}
                isSelected={kind === option.value}
                onSelect={() => setKind(option.value)}
              />
            ))}
          </div>
        </fieldset>

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-1 basis-64 flex-col gap-1.5 text-sm font-semibold text-navy">
            <span>
              {kind === 'questions' ? 'Roles' : 'Tags'}{' '}
              <span className="font-normal text-body">(optional, separated by commas)</span>
            </span>
            <input
              value={tags}
              onChange={(event) => setTags(event.target.value)}
              maxLength={200}
              placeholder={kind === 'questions' ? 'Backend Engineer' : 'backend, python'}
              className="h-11.5 rounded-2xl border-[1.5px] border-line px-3.5 text-[15px] font-normal text-navy placeholder:text-body/60"
            />
            {kind === 'questions' && (
              <span className="text-xs font-normal leading-relaxed text-body">
                Type the job title, such as Backend Engineer. Separate several roles with commas.
                Leave empty for general questions.
              </span>
            )}
          </label>
          <Button type="submit" disabled={!file || isUploading}>
            <Upload className="size-4.5" aria-hidden="true" />
            {isUploading ? 'Uploading…' : 'Upload document'}
          </Button>
        </div>

        {error && (
          <p role="alert" className="text-sm font-semibold text-danger">
            {error}
          </p>
        )}
      </div>
    </form>
  )
}
