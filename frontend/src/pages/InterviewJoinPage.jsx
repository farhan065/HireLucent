import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router'
import CandidateLayout from '../components/join/CandidateLayout.jsx'
import LinkEnded from '../components/join/LinkEnded.jsx'
import PreJoin from '../components/join/PreJoin.jsx'
import WaitingRoom from '../components/join/WaitingRoom.jsx'
import Skeleton from '../components/Skeleton.jsx'
import { useDevicePreview } from '../hooks/useDevicePreview.js'
import { checkIn, enterWaitingRoom, leaveWaitingRoom, readLink } from '../lib/join.js'

const LINK_REFRESH_MS = 15 * 1000
const CHECK_IN_MS = 5 * 1000
const TICK_MS = 10 * 1000

function useNow(intervalMs) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

// A link that works: the camera check and Join, then the waiting room.
// The camera is only asked for here, never on a link that no longer works.
function JoinFlow({ token, link, onGone }) {
  const preview = useDevicePreview()
  const now = useNow(TICK_MS)
  // The candidate's pass for this interview, once they joined.
  const [pass, setPass] = useState(null)
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState('')

  async function handleJoin() {
    setIsBusy(true)
    setError('')
    try {
      setPass(await enterWaitingRoom(token))
    } catch (joinError) {
      if (joinError.status === 404) onGone()
      else setError(joinError.message)
    } finally {
      setIsBusy(false)
    }
  }

  async function handleLeave() {
    setIsBusy(true)
    await leaveWaitingRoom(pass).catch(() => null)
    setPass(null)
    setIsBusy(false)
  }

  // While waiting, check in every few seconds. The interview room that
  // opens when the interviewer lets the candidate in comes in step 4.7.
  useEffect(() => {
    if (!pass) return undefined
    function check() {
      checkIn(pass)
        .then((state) => state === 'ended' && onGone())
        .catch((checkError) => {
          if (checkError.status === 401 || checkError.status === 404) onGone()
        })
    }
    const timer = setInterval(check, CHECK_IN_MS)
    return () => clearInterval(timer)
  }, [pass, onGone])

  if (pass) {
    return (
      <WaitingRoom
        link={link}
        preview={preview}
        now={now}
        isLeaving={isBusy}
        onLeave={handleLeave}
      />
    )
  }
  return (
    <PreJoin
      link={link}
      preview={preview}
      now={now}
      isBusy={isBusy}
      error={error}
      onJoin={handleJoin}
    />
  )
}

// The candidate's private interview link: /interview/<token>. No sign-in.
export default function InterviewJoinPage() {
  const { token } = useParams()
  const [link, setLink] = useState(null)
  const [isGone, setIsGone] = useState(false)
  const [error, setError] = useState('')
  const handleGone = useCallback(() => setIsGone(true), [])

  // Read the link now and again every few seconds, so Join opens and a
  // cancelled interview is noticed without reloading.
  useEffect(() => {
    let isCurrent = true
    function load() {
      readLink(token)
        .then((loaded) => {
          if (!isCurrent) return
          setLink(loaded)
          setError('')
          if (loaded.state === 'ended') setIsGone(true)
        })
        .catch((loadError) => {
          if (!isCurrent) return
          if (loadError.status === 404 || loadError.status === 422) setIsGone(true)
          else setError(loadError.message)
        })
    }
    load()
    const timer = setInterval(load, LINK_REFRESH_MS)
    return () => {
      isCurrent = false
      clearInterval(timer)
    }
  }, [token])

  if (isGone) return <LinkEnded />
  if (!link) {
    return (
      <CandidateLayout note="Interview invitation">
        {error ? (
          <p role="alert" className="font-semibold text-danger">
            {error}
          </p>
        ) : (
          <div role="status" aria-label="Opening your invitation" className="flex flex-col gap-6">
            <Skeleton className="h-10 w-96 max-w-full" />
            <Skeleton className="h-96 w-full rounded-card" />
          </div>
        )}
      </CandidateLayout>
    )
  }
  return <JoinFlow token={token} link={link} onGone={handleGone} />
}
