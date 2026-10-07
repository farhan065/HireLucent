import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from '../lib/api.js'

const REFRESH_MS = 3000

// The Knowledge Base documents, with upload and delete. While a document is
// still being processed the list is reloaded every few seconds.
export function useDocuments() {
  const [documents, setDocuments] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(
    () =>
      apiRequest('/knowledge/documents')
        .then((loaded) => {
          setDocuments(loaded)
          setError('')
        })
        .catch((loadError) => setError(loadError.message)),
    [],
  )

  useEffect(() => {
    load()
  }, [load])

  const isProcessing = documents?.some((document) => document.status === 'processing')
  useEffect(() => {
    if (!isProcessing) return undefined
    const timer = setInterval(load, REFRESH_MS)
    return () => clearInterval(timer)
  }, [isProcessing, load])

  async function upload(file, kind, tags) {
    const form = new FormData()
    form.append('file', file)
    form.append('doc_type', kind)
    form.append('tags', tags)
    const created = await apiRequest('/knowledge/documents', { method: 'POST', body: form })
    setDocuments((current) => [created, ...(current ?? [])])
  }

  async function remove(documentId) {
    await apiRequest(`/knowledge/documents/${documentId}`, { method: 'DELETE' })
    setDocuments((current) => current.filter((document) => document.id !== documentId))
  }

  return { documents, error, upload, remove }
}
