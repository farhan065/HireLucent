import { useCallback, useEffect, useRef, useState } from 'react'
import { Room, RoomEvent } from 'livekit-client'
import { apiRequest } from '../lib/api.js'

const CAMERA_BUSY =
  'Your camera is in use by another tab, so you joined with the microphone only.'

// Joins the temporary video test room and keeps the list of tracks to show.
// Removed together with the test page when the interview room is built.
export function useTestRoom() {
  const roomRef = useRef(null)
  const [state, setState] = useState('disconnected')
  const [tracks, setTracks] = useState([])
  const [notice, setNotice] = useState(null)
  const [error, setError] = useState(null)

  const addTrack = useCallback((track, participant, isLocal) => {
    setTracks((current) => [
      ...current.filter((item) => item.track !== track),
      { track, identity: participant.identity, isLocal },
    ])
  }, [])

  const removeTrack = useCallback((track) => {
    setTracks((current) => current.filter((item) => item.track !== track))
  }, [])

  const join = useCallback(async () => {
    setError(null)
    setNotice(null)
    const room = new Room({ adaptiveStream: true, dynacast: true })
    roomRef.current = room
    room
      .on(RoomEvent.ConnectionStateChanged, setState)
      .on(RoomEvent.TrackSubscribed, (track, _pub, participant) =>
        addTrack(track, participant, false),
      )
      .on(RoomEvent.TrackUnsubscribed, removeTrack)
      .on(RoomEvent.LocalTrackPublished, (pub, participant) =>
        addTrack(pub.track, participant, true),
      )
      .on(RoomEvent.LocalTrackUnpublished, (pub) => removeTrack(pub.track))
      .on(RoomEvent.Disconnected, () => setTracks([]))

    try {
      const { url, token } = await apiRequest('/video/test-token', { method: 'POST' })
      await room.connect(url, token)
    } catch (err) {
      setError(err.message || 'Could not join the test room.')
      await room.disconnect()
      return
    }
    try {
      await room.localParticipant.enableCameraAndMicrophone()
    } catch {
      // On one computer, a second tab may not get the camera.
      await room.localParticipant.setMicrophoneEnabled(true).catch(() => {})
      setNotice(CAMERA_BUSY)
    }
  }, [addTrack, removeTrack])

  const leave = useCallback(() => roomRef.current?.disconnect(), [])

  // Leave the room when the page is closed or left.
  useEffect(() => () => void roomRef.current?.disconnect(), [])

  return { state, tracks, notice, error, join, leave }
}
