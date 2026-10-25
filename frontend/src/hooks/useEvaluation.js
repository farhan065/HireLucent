import { useCallback, useEffect, useRef, useState } from 'react'
import {
  checkClaims,
  checkQuality,
  evaluateAll,
  evaluateInterview,
  readEvaluation,
  writeReport,
} from '../lib/assessment.js'

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
  // reportOnly, only the report of an evaluated interview is written; with
  // claimsOnly, only its CV claims are checked; with qualityOnly, only its
  // interview quality (F10).
  async function start(
    sessionId,
    { reportOnly = false, claimsOnly = false, qualityOnly = false } = {},
  ) {
    setError('')
    try {
      const task = await (qualityOnly
        ? checkQuality(sessionId)
        : claimsOnly
          ? checkClaims(sessionId)
          : reportOnly
            ? writeReport(sessionId)
            : sessionId
              ? evaluateInterview(sessionId)
              : evaluateAll(jobId))
      const ids = sessionId ? [sessionId] : []
      const result = { session_ids: ids, current: sessionId ?? null }
      setActivity((current) => ({
        ...current,
        running: {
          ...task,
          result: claimsOnly
            ? { ...result, claims_only: true }
            : qualityOnly
              ? { ...result, quality_only: true }
              : result,
        },
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
