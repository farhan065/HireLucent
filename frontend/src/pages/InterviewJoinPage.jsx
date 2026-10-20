import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router'
import CandidateLayout from '../components/join/CandidateLayout.jsx'
import IdentityCapture from '../components/join/IdentityCapture.jsx'
import LinkEnded from '../components/join/LinkEnded.jsx'
import PinEntry from '../components/join/PinEntry.jsx'
import PreJoin from '../components/join/PreJoin.jsx'
import ThankYou from '../components/join/ThankYou.jsx'
import WaitingRoom from '../components/join/WaitingRoom.jsx'
import Skeleton from '../components/Skeleton.jsx'
import { useDevicePreview } from '../hooks/useDevicePreview.js'
import { checkIn, enterWaitingRoom, joinRoom, leaveWaitingRoom, readLink } from '../lib/join.js'

// The video library is loaded only once the candidate is let in.
const CandidateRoom = lazy(() => import('../components/join/CandidateRoom.jsx'))

const LINK_REFRESH_MS = 15 * 1000
const CHECK_IN_MS = 3 * 1000
const TICK_MS = 10 * 1000

function useNow(intervalMs) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

// A link that works: the camera check and Join, the identity photo (for an
// interview with a PIN), the waiting room, then the interview room once the
// interviewer lets the candidate in. The camera is only asked for here,
// never on a link that no longer works.
function JoinFlow({ token, link, pin, onEnded, onRoomChange, onPinRejected }) {
  // The candidate's pass for this interview, once they joined, and their
  // pass for the video room, once they were let in.
  const [pass, setPass] = useState(null)
  // The identity photo: "needed", "taken", "skipped", or null for none.
  const [photo, setPhoto] = useState(null)
  const [connection, setConnection] = useState(null)
  const preview = useDevicePreview(!connection)
  const now = useNow(TICK_MS)
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState('')
  const { cameraId, microphoneId } = preview

  async function handleJoin() {
    setIsBusy(true)
    setError('')
    try {
      const joined = await enterWaitingRoom(token, pin)
      if (joined.photoNeeded) setPhoto('needed')
      setPass(joined.pass)
    } catch (joinError) {
      if (joinError.status === 404) onEnded(false)
      else if (joinError.status === 401) onPinRejected()
      else setError(joinError.message)
    } finally {
      setIsBusy(false)
    }
  }

  async function handleLeaveWaiting() {
    setIsBusy(true)
    await leaveWaitingRoom(pass).catch(() => null)
    setPass(null)
    setIsBusy(false)
  }

  const handleLeftRoom = useCallback(() => {
    setConnection(null)
    setPass(null)
    onRoomChange(false)
  }, [onRoomChange])

  const handleRoomEnded = useCallback(() => onEnded(true), [onEnded])
  // A fresh room pass to rejoin after the connection was lost.
  const renewRoomPass = useCallback(() => joinRoom(pass), [pass])

  // While joined, check in every few seconds: still waiting, let in, or
  // ended. Being let in opens the room with the chosen camera and microphone.
  useEffect(() => {
    if (!pass) return undefined
    const isInRoom = Boolean(connection)
    function check() {
      checkIn(pass)
        .then(async (state) => {
          if (state === 'ended') onEnded(isInRoom)
          if (state === 'started' && !isInRoom) {
            const roomPass = await joinRoom(pass)
            setConnection({ ...roomPass, cameraId, microphoneId })
            onRoomChange(true)
          }
        })
        .catch((checkError) => {
          if (checkError.status === 401 || checkError.status === 404) onEnded(isInRoom)
        })
    }
    check()
    const timer = setInterval(check, CHECK_IN_MS)
    return () => clearInterval(timer)
  }, [pass, connection, cameraId, microphoneId, onEnded, onRoomChange])

  if (connection) {
    return (
      <Suspense fallback={null}>
        <CandidateRoom
          link={link}
          connection={connection}
          renewPass={renewRoomPass}
          onLeft={handleLeftRoom}
          onEnded={handleRoomEnded}
        />
      </Suspense>
    )
  }
  if (pass && photo === 'needed') {
    return (
      <IdentityCapture
        link={link}
        preview={preview}
        pass={pass}
        onDone={setPhoto}
        onEnded={() => onEnded(false)}
      />
    )
  }
  if (pass) {
    return (
      <WaitingRoom
        link={link}
        preview={preview}
        now={now}
        photo={photo}
        isLeaving={isBusy}
        onLeave={handleLeaveWaiting}
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
  // How the page ends: "gone" for a link that no longer works, "thanks"
  // after an interview the candidate took part in.
  const [ending, setEnding] = useState(null)
  const [isInRoom, setIsInRoom] = useState(false)
  const [error, setError] = useState('')
  // The PIN, kept only in this page while it is open.
  const [pin, setPin] = useState(null)
  const handleEnded = useCallback(
    (wasInRoom) => setEnding((current) => current ?? (wasInRoom ? 'thanks' : 'gone')),
    [],
  )

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
          if (loaded.state === 'ended') handleEnded(isInRoom)
        })
        .catch((loadError) => {
          if (!isCurrent) return
          if (loadError.status === 404 || loadError.status === 422) handleEnded(isInRoom)
          else setError(loadError.message)
        })
    }
    load()
    const timer = setInterval(load, LINK_REFRESH_MS)
    return () => {
      isCurrent = false
      clearInterval(timer)
    }
  }, [token, isInRoom, handleEnded])

  if (ending === 'thanks') {
    return <ThankYou firstName={link?.first_name} jobTitle={link?.job_title} />
  }
  if (ending === 'gone') return <LinkEnded />
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
  if (link.pin_required && !pin) {
    return (
      <PinEntry token={token} link={link} onAccepted={setPin} onEnded={() => handleEnded(false)} />
    )
  }
  return (
    <JoinFlow
      token={token}
      link={link}
      pin={pin}
      onEnded={handleEnded}
      onRoomChange={setIsInRoom}
      onPinRejected={() => setPin(null)}
    />
  )
}
