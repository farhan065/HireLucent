import { useCallback, useEffect, useRef, useState } from 'react'
import { evaluateAll, evaluateInterview, readEvaluation, writeReport } from '../lib/assessment.js'

const POLL_MS = 2000

// A job's interview evaluations: the one running, the last finished one and
// how many completed interviews wait. While one runs it is asked again every
// two seconds, so progress also shows after a page reload. onFinished is
// called when a run ends. Nothing loads while jobId is empty.
export function useEvaluation(jobId, onFinished) {
  const [activity, setActivity] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!jobId) return Promise.resolve()
    return readEvaluation(jobId)
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

  // One interview when sessionId is given, otherwise every new one. With
  // reportOnly, only the report of an evaluated interview is written.
  async function start(sessionId, { reportOnly = false } = {}) {
    setError('')
    try {
      const task = await (reportOnly
        ? writeReport(sessionId)
        : sessionId
          ? evaluateInterview(sessionId)
          : evaluateAll(jobId))
      const ids = sessionId ? [sessionId] : []
      setActivity((current) => ({
        ...current,
        running: { ...task, result: { session_ids: ids, current: sessionId ?? null } },
      }))
      load()
    } catch (startError) {
      setError(startError.message)
    }
  }

  return {
    activity,
    isLoaded: activity !== null,
    isRunning: Boolean(runningId),
    error,
    start,
    reload: load,
  }
}
