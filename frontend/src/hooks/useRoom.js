import { useCallback, useEffect, useRef, useState } from 'react'
import { ConnectionQuality, DisconnectReason, Room, RoomEvent, Track } from 'livekit-client'

const CAMERA_BUSY =
  'Your camera is in use by another tab or app, so you joined with the microphone only.'

// Waits between attempts to rejoin after the connection was lost, in ms.
const RETRY_DELAYS = [2000, 4000, 8000]
const RETRY_DELAY_MAX = 10000

const EVENTS = [
  RoomEvent.TrackSubscribed,
  RoomEvent.TrackUnsubscribed,
  RoomEvent.LocalTrackPublished,
  RoomEvent.LocalTrackUnpublished,
  RoomEvent.TrackMuted,
  RoomEvent.TrackUnmuted,
  RoomEvent.ParticipantConnected,
  RoomEvent.ParticipantDisconnected,
]

function track(participant, source) {
  return participant?.getTrackPublication(source)?.track ?? null
}

// Everything the screen shows, read from the room after each change.
function snapshot(room) {
  const local = room.localParticipant
  const remote = [...room.remoteParticipants.values()][0] ?? null
  return {
    localCamera: track(local, Track.Source.Camera),
    localScreen: track(local, Track.Source.ScreenShare),
    remoteCamera: track(remote, Track.Source.Camera),
    remoteScreen: track(remote, Track.Source.ScreenShare),
    remoteAudio: [
      track(remote, Track.Source.Microphone),
      track(remote, Track.Source.ScreenShareAudio),
    ].filter(Boolean),
    remoteName: remote?.name ?? '',
    isRemoteHere: Boolean(remote),
    isRemoteMuted: Boolean(remote?.getTrackPublication(Track.Source.Microphone)?.isMuted),
    isMicrophoneOn: local.isMicrophoneEnabled,
    isCameraOn: local.isCameraEnabled,
    isSharing: local.isScreenShareEnabled,
  }
}

const EMPTY = {
  localCamera: null,
  localScreen: null,
  remoteCamera: null,
  remoteScreen: null,
  remoteAudio: [],
  remoteName: '',
  isRemoteHere: false,
  isRemoteMuted: false,
  isMicrophoneOn: false,
  isCameraOn: false,
  isSharing: false,
}

function retryDelay(attempt) {
  return RETRY_DELAYS[attempt] ?? RETRY_DELAY_MAX
}

// One person in one interview's video room. "connection" is the room pass
// ({ url, token }) with the chosen camera and microphone, or null to stay
// out. "renewPass" asks the backend for a fresh pass, used to rejoin.
//
// Short drops are recovered by LiveKit itself. If it gives up, this hook
// keeps rejoining with a fresh pass for as long as the interview runs, and
// restores the microphone and camera as they were. Leaving the page leaves
// the room.
export function useRoom(connection, renewPass) {
  const roomRef = useRef(null)
  const passRef = useRef(null)
  // The microphone and camera as the person last set them.
  const devicesRef = useRef({ microphone: true, camera: true })
  const [view, setView] = useState(EMPTY)
  const [state, setState] = useState('connecting')
  // "ended" when the room was closed because the interview ended.
  const [endReason, setEndReason] = useState(null)
  const [notice, setNotice] = useState('')
  // When this person's connection dropped, and when the other person's did.
  const [lostAt, setLostAt] = useState(null)
  const [remoteLostAt, setRemoteLostAt] = useState(null)
  // Rejoining: how many tries so far, and a counter that opens a new room.
  const [retries, setRetries] = useState(0)
  const [joinCount, setJoinCount] = useState(0)

  useEffect(() => {
    if (!connection) return undefined
    const pass = passRef.current ?? connection
    const room = new Room({
      adaptiveStream: true,
      dynacast: true,
      videoCaptureDefaults: { deviceId: connection.cameraId || undefined },
      audioCaptureDefaults: { deviceId: connection.microphoneId || undefined },
    })
    roomRef.current = room
    let isCurrent = true
    // The devices are remembered only once they were switched on as wanted,
    // so a change in the room while joining cannot switch them off.
    let isReady = false
    const update = () => {
      if (!isCurrent) return
      const next = snapshot(room)
      if (isReady && room.state === 'connected') {
        devicesRef.current = { microphone: next.isMicrophoneOn, camera: next.isCameraOn }
      }
      setView(next)
    }
    const lose = () => isCurrent && setLostAt((at) => at ?? Date.now())

    EVENTS.forEach((event) => room.on(event, update))
    room.on(RoomEvent.ConnectionStateChanged, (next) => isCurrent && setState(next))
    room.on(RoomEvent.Reconnecting, lose)
    room.on(RoomEvent.SignalReconnecting, lose)
    room.on(RoomEvent.Reconnected, () => isCurrent && setLostAt(null))
    room.on(RoomEvent.ParticipantDisconnected, () => {
      if (isCurrent) setRemoteLostAt((at) => at ?? Date.now())
    })
    room.on(RoomEvent.ParticipantConnected, () => isCurrent && setRemoteLostAt(null))
    room.on(RoomEvent.ConnectionQualityChanged, (quality, participant) => {
      if (!isCurrent || participant.isLocal) return
      if (quality === ConnectionQuality.Lost) setRemoteLostAt((at) => at ?? Date.now())
      else setRemoteLostAt(null)
    })
    room.on(RoomEvent.Disconnected, (reason) => {
      if (!isCurrent) return
      setView(EMPTY)
      if (reason === DisconnectReason.ROOM_DELETED) setEndReason('ended')
      else if (reason === DisconnectReason.DUPLICATE_IDENTITY) setState('replaced')
      else if (reason !== DisconnectReason.CLIENT_INITIATED) {
        setState('lost')
        lose()
      }
    })

    async function join() {
      const { microphone, camera } = devicesRef.current
      try {
        await room.connect(pass.url, pass.token)
      } catch {
        if (!isCurrent) return
        setState('lost')
        lose()
        setRetries((count) => count + 1)
        return
      }
      if (!isCurrent) return
      setLostAt(null)
      setRetries(0)
      // Whoever is already in the room is here; a drop is noticed later.
      if (room.remoteParticipants.size > 0) setRemoteLostAt(null)
      try {
        await room.localParticipant.setCameraEnabled(camera)
      } catch {
        if (isCurrent) setNotice(CAMERA_BUSY)
      }
      await room.localParticipant.setMicrophoneEnabled(microphone).catch(() => null)
      isReady = true
      update()
    }
    join()

    return () => {
      isCurrent = false
      room.disconnect()
    }
  }, [connection, joinCount])

  // Get a fresh pass and open the room again. An interview that ended
  // meanwhile refuses the pass, which ends the room here too.
  const rejoin = useCallback(async () => {
    if (!renewPass) return
    try {
      passRef.current = await renewPass()
      setJoinCount((count) => count + 1)
    } catch (renewError) {
      if ([401, 404, 409].includes(renewError.status)) setEndReason('ended')
      else setRetries((count) => count + 1)
    }
  }, [renewPass])

  // While the connection is lost, try again after a growing wait, and at
  // once when the computer reports it is back online.
  useEffect(() => {
    if (state !== 'lost' || endReason) return undefined
    const timer = setTimeout(rejoin, retryDelay(retries))
    window.addEventListener('online', rejoin)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('online', rejoin)
    }
  }, [state, endReason, retries, rejoin])

  const run = useCallback(async (action) => {
    const room = roomRef.current
    if (!room) return
    try {
      await action(room.localParticipant)
    } catch {
      // A cancelled screen picker or a refused camera changes nothing.
    }
    const next = snapshot(room)
    devicesRef.current = { microphone: next.isMicrophoneOn, camera: next.isCameraOn }
    setView(next)
  }, [])

  return {
    ...view,
    state,
    endReason,
    notice,
    lostAt: state === 'connected' ? null : lostAt,
    remoteLostAt,
    isReplaced: state === 'replaced',
    rejoin,
    toggleMicrophone: () =>
      run((local) => local.setMicrophoneEnabled(!local.isMicrophoneEnabled)),
    toggleCamera: () => run((local) => local.setCameraEnabled(!local.isCameraEnabled)),
    toggleScreenShare: () =>
      run((local) => local.setScreenShareEnabled(!local.isScreenShareEnabled, { audio: true })),
    leave: () => roomRef.current?.disconnect(),
  }
}
