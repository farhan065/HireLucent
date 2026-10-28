import { useCallback, useEffect, useRef, useState } from 'react'
import { readFeedbackActivity, sendAllPassed, writeEmails } from '../lib/feedback.js'

const POLL_MS = 2000

// A job's feedback emails: the writing or sending running now, the last
// finished one, and how many emails are still to send per stage. While one
// runs it is asked again every two seconds; onFinished is called when it
// ends, so the lists load again. Nothing loads while jobId is empty.
export function useFeedback(jobId, onFinished) {
  const [activity, setActivity] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!jobId) return Promise.resolve()
    return readFeedbackActivity(jobId)
      .then((loaded) => {
        setActivity(loaded)
        setError('')
      })
      .catch((loadError) => setError(loadError.message))
  }, [jobId])

  useEffect(() => {
    load()
  }, [load])

  const runningId = activity?.running?.id
  useEffect(() => {
    if (!runningId) return undefined
    const timer = setInterval(load, POLL_MS)
    return () => clearInterval(timer)
  }, [runningId, load])

  const wasRunning = useRef(false)
  useEffect(() => {
    if (wasRunning.current && !runningId) onFinished?.()
    wasRunning.current = Boolean(runningId)
  }, [runningId, onFinished])

  async function start(call, ids = []) {
    setError('')
    try {
      const task = await call()
      setActivity((current) => ({
        ...current,
        running: { ...task, result: { candidate_ids: ids, current: ids[0] ?? null } },
      }))
      load()
      return true
    } catch (startError) {
      setError(startError.message)
      return false
    }
  }

  return {
    activity,
    isLoaded: activity !== null,
    isRunning: Boolean(runningId),
    error,
    write: (candidateIds) => start(() => writeEmails(jobId, candidateIds), candidateIds),
    sendAll: (stage) => start(() => sendAllPassed(jobId, stage)),
    reload: load,
  }
}
