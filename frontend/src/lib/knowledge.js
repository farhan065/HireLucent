// The kinds of document the Knowledge Base holds, and the upload limits.
// The limits match the checks the backend makes.

export const DOCUMENT_KINDS = [
  {
    value: 'jd_template',
    label: 'JD template',
    plural: 'JD templates',
    description: 'A job description to follow for structure and tone.',
    usedFor: 'Used when drafting a job',
    tone: 'bg-violet-soft text-violet',
  },
  {
    value: 'reference',
    label: 'Reference',
    plural: 'References',
    description: 'Company or technical material, such as a tech handbook.',
    usedFor: 'Used in interviews',
    tone: 'bg-teal-soft text-teal',
  },
  {
    value: 'questions',
    label: 'Question bank',
    plural: 'Question banks',
    description: 'Interview questions with expected answers.',
    usedFor: 'Used in interviews',
    tone: 'bg-amber-soft text-amber',
  },
]

export const KIND_BY_VALUE = Object.fromEntries(
  DOCUMENT_KINDS.map((kind) => [kind.value, kind]),
)

export const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md']
export const MAX_UPLOAD_MB = 10

// Returns why a file cannot be uploaded, or an empty string if it can.
export function fileProblem(file) {
  const name = file.name.toLowerCase()
  if (!ACCEPTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return 'Choose a PDF, DOCX, TXT or Markdown file.'
  }
  if (file.size === 0) return 'This file is empty.'
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    return `This file is larger than ${MAX_UPLOAD_MB} MB.`
  }
  return ''
}

export function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
