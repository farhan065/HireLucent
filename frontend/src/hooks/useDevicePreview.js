import { useEffect, useState } from 'react'

const MESSAGES = {
  NotAllowedError:
    'Allow camera and microphone access for this page in your browser, then reload it.',
  NotFoundError: 'No camera or microphone was found. Connect one, then reload this page.',
  NotReadableError: 'Your camera or microphone is being used by another app. Close it and reload.',
}
const UNSUPPORTED = 'This browser cannot use a camera here. Open the link in a recent Chrome, Edge or Firefox.'

function constraint(deviceId) {
  return deviceId ? { deviceId: { exact: deviceId } } : true
}

// The candidate's own camera and microphone before and while they wait:
// the preview, the device lists, on/off switches and a microphone level.
// Nothing is recorded or sent anywhere; it stays in this browser. When
// "isEnabled" is false (in the interview room) the camera is released.
export function useDevicePreview(isEnabled = true) {
  const [stream, setStream] = useState(null)
  const [devices, setDevices] = useState({ cameras: [], microphones: [] })
  const [cameraId, setCameraId] = useState('')
  const [microphoneId, setMicrophoneId] = useState('')
  const [cameraOn, setCameraOn] = useState(true)
  const [microphoneOn, setMicrophoneOn] = useState(true)
  const [level, setLevel] = useState(0)
  const [heardSound, setHeardSound] = useState(false)
  const [error, setError] = useState(() =>
    navigator.mediaDevices?.getUserMedia ? '' : UNSUPPORTED,
  )

  // Open the chosen camera and microphone, and list the others.
  useEffect(() => {
    if (!isEnabled || !navigator.mediaDevices?.getUserMedia) return undefined
    let opened = null
    let isCurrent = true
    navigator.mediaDevices
      .getUserMedia({ video: constraint(cameraId), audio: constraint(microphoneId) })
      .then(async (media) => {
        if (!isCurrent) {
          media.getTracks().forEach((track) => track.stop())
          return
        }
        opened = media
        setStream(media)
        setError('')
        const list = await navigator.mediaDevices.enumerateDevices()
        setDevices({
          cameras: list.filter((item) => item.kind === 'videoinput'),
          microphones: list.filter((item) => item.kind === 'audioinput'),
        })
      })
      .catch((openError) => {
        if (isCurrent) setError(MESSAGES[openError.name] ?? MESSAGES.NotReadableError)
      })
    return () => {
      isCurrent = false
      opened?.getTracks().forEach((track) => track.stop())
    }
  }, [isEnabled, cameraId, microphoneId])

  // The on/off switches only mute the tracks, so turning back on is instant.
  useEffect(() => {
    stream?.getVideoTracks().forEach((track) => {
      track.enabled = cameraOn
    })
    stream?.getAudioTracks().forEach((track) => {
      track.enabled = microphoneOn
    })
  }, [stream, cameraOn, microphoneOn])

  // The microphone level, measured about ten times a second.
  useEffect(() => {
    if (!stream?.getAudioTracks().length) return undefined
    const context = new AudioContext()
    const analyser = context.createAnalyser()
    analyser.fftSize = 512
    context.createMediaStreamSource(stream).connect(analyser)
    const samples = new Uint8Array(analyser.fftSize)
    const timer = setInterval(() => {
      analyser.getByteTimeDomainData(samples)
      let sum = 0
      for (const sample of samples) sum += ((sample - 128) / 128) ** 2
      const value = Math.min(1, Math.sqrt(sum / samples.length) * 4)
      setLevel(value)
      if (value > 0.08) setHeardSound(true)
    }, 100)
    return () => {
      clearInterval(timer)
      context.close()
    }
  }, [stream])

  const videoTrack = stream?.getVideoTracks()[0]
  const audioTrack = stream?.getAudioTracks()[0]
  return {
    stream,
    devices,
    cameraId: cameraId || videoTrack?.getSettings().deviceId || '',
    microphoneId: microphoneId || audioTrack?.getSettings().deviceId || '',
    setCameraId,
    setMicrophoneId,
    cameraOn,
    microphoneOn,
    toggleCamera: () => setCameraOn((on) => !on),
    toggleMicrophone: () => setMicrophoneOn((on) => !on),
    level: microphoneOn ? level : 0,
    cameraWorks: Boolean(videoTrack) && cameraOn,
    microphoneWorks: Boolean(audioTrack) && microphoneOn && heardSound,
    hasMicrophone: Boolean(audioTrack),
    error,
  }
}
