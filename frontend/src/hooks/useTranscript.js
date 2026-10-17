import { useCallback, useEffect, useState } from 'react'
import { readTranscript } from '../lib/room.js'

// The live transcript arrives on this topic from the hidden transcription
// worker. The video server removes the sender's identity from data sent by a
// hidden participant and always sets it for everyone else, so data with no
// sender can only come from the worker: the candidate cannot send lines.
const TOPIC = 'transcript'
// The worker sends its status every 5 seconds. Without one for this long,
// transcription is taken to be not working.
const SILENCE_MS = 15 * 1000

function byTime(a, b) {
  return a.start_ms - b.start_ms || a.id - b.id
}

// The interviewer's live transcript. Saved turns load first, and again after
// each reconnect, so nothing said while the page was away is missed. Then
// each new turn, the words still being spoken and the worker's status
// arrive over the room. "state" is "waiting" (not started), "loading",
// "listening", "paused" (speech-to-text reconnecting) or "off".
export function useTranscript(sessionId, room, isStarted) {
  const [turns, setTurns] = useState([])
  // Per speaker, the words of the turn still being spoken: { text, start_ms }.
  const [live, setLive] = useState({})
  const [isLoaded, setIsLoaded] = useState(false)
  const [status, setStatus] = useState(null)
  const [heardAt, setHeardAt] = useState(0)
  const [isSilent, setIsSilent] = useState(false)

  const isConnected = room.state === 'connected'
  const { onData } = room

  const merge = useCallback((items) => {
    setTurns((current) => {
      const known = new Map(current.map((turn) => [turn.id, turn]))
      items.forEach((turn) => known.set(turn.id, turn))
      return [...known.values()].sort(byTime)
    })
  }, [])

  useEffect(() => {
    if (!isStarted || !isConnected) return undefined
    let isCurrent = true
    readTranscript(sessionId)
      .then((transcript) => isCurrent && merge(transcript.turns))
      .catch(() => null)
      .finally(() => isCurrent && setIsLoaded(true))
    return () => {
      isCurrent = false
    }
  }, [sessionId, isStarted, isConnected, merge])

  useEffect(
    () =>
      onData(TOPIC, (payload, identity) => {
        if (identity) return
        let event
        try {
          event = JSON.parse(new TextDecoder().decode(payload))
        } catch {
          return
        }
        if (event.type === 'turn') {
          merge([event])
        } else if (event.type === 'live') {
          const words = event.text ? { text: event.text, start_ms: event.start_ms } : null
          setLive((current) => ({ ...current, [event.speaker]: words }))
        } else if (event.type === 'status') {
          setStatus(event.state)
          setHeardAt(Date.now())
          setIsSilent(false)
        }
      }),
    [onData, merge],
  )

  // Each status starts the wait again; a wait that runs out means the
  // worker is not running.
  useEffect(() => {
    if (!isStarted || !isConnected) return undefined
    const timer = setTimeout(() => setIsSilent(true), SILENCE_MS)
    return () => clearTimeout(timer)
  }, [isStarted, isConnected, heardAt])

  let state = 'listening'
  if (!isStarted) state = 'waiting'
  else if (!isLoaded) state = 'loading'
  else if (isSilent || status === 'off') state = 'off'
  else if (status === 'paused') state = 'paused'

  return { turns, live: state === 'off' ? {} : live, state }
}
