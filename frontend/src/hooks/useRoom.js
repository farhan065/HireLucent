import { useCallback, useEffect, useRef, useState } from 'react'
import { DisconnectReason, Room, RoomEvent, Track } from 'livekit-client'

const CAMERA_BUSY =
  'Your camera is in use by another tab or app, so you joined with the microphone only.'
const CANNOT_CONNECT =
  'The video room could not be reached. Check your connection and reload the page.'

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

// One person in one interview's video room. "connection" is the room pass
// ({ url, token }) with the chosen camera and microphone, or null to stay
// out. Leaving the page leaves the room.
export function useRoom(connection) {
  const roomRef = useRef(null)
  const [view, setView] = useState(EMPTY)
  const [state, setState] = useState('connecting')
  // "ended" when the room was closed because the interview ended.
  const [endReason, setEndReason] = useState(null)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!connection) return undefined
    const room = new Room({
      adaptiveStream: true,
      dynacast: true,
      videoCaptureDefaults: { deviceId: connection.cameraId || undefined },
      audioCaptureDefaults: { deviceId: connection.microphoneId || undefined },
    })
    roomRef.current = room
    let isCurrent = true
    const update = () => isCurrent && setView(snapshot(room))
    EVENTS.forEach((event) => room.on(event, update))
    room.on(RoomEvent.ConnectionStateChanged, (next) => isCurrent && setState(next))
    room.on(RoomEvent.Disconnected, (reason) => {
      if (!isCurrent) return
      if (reason === DisconnectReason.ROOM_DELETED) setEndReason('ended')
      setView(EMPTY)
    })

    async function join() {
      try {
        await room.connect(connection.url, connection.token)
      } catch {
        if (isCurrent) setError(CANNOT_CONNECT)
        return
      }
      try {
        await room.localParticipant.enableCameraAndMicrophone()
      } catch {
        await room.localParticipant.setMicrophoneEnabled(true).catch(() => null)
        if (isCurrent) setNotice(CAMERA_BUSY)
      }
      update()
    }
    join()

    return () => {
      isCurrent = false
      room.disconnect()
    }
  }, [connection])

  const run = useCallback(async (action) => {
    const room = roomRef.current
    if (!room) return
    try {
      await action(room.localParticipant)
    } catch {
      // A cancelled screen picker or a refused camera changes nothing.
    }
    setView(snapshot(room))
  }, [])

  return {
    ...view,
    state,
    endReason,
    notice,
    error,
    toggleMicrophone: () =>
      run((local) => local.setMicrophoneEnabled(!local.isMicrophoneEnabled)),
    toggleCamera: () => run((local) => local.setCameraEnabled(!local.isCameraEnabled)),
    toggleScreenShare: () =>
      run((local) => local.setScreenShareEnabled(!local.isScreenShareEnabled, { audio: true })),
    leave: () => roomRef.current?.disconnect(),
  }
}
