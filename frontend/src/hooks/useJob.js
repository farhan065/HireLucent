import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from '../lib/api.js'
import { loadWaiting } from '../lib/jobs.js'

// One job with what its pages need: the job, its conversation with the
// AI Agent and the number of new applications waiting. It loads again when
// refreshKey changes, for example when the job has just been published.
export function useJob(jobId, refreshKey) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!jobId) return Promise.resolve()
    return Promise.all([apiRequest(`/jobs/${jobId}`), apiRequest('/chat/conversations')])
      .then(async ([job, conversations]) => {
        const conversation = conversations.find((item) => item.job_id === job.id)
        const waiting = await loadWaiting(job)
        setData({ job, threadId: conversation?.thread_id, waiting })
        setError('')
      })
      .catch((loadError) => setError(loadError.message))
  }, [jobId])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  return { ...data, error, reload: load }
}
