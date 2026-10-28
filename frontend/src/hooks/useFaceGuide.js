import { useEffect, useRef, useState } from 'react'
import { guideTip } from '../lib/faceGuide.js'

// MediaPipe's runtime and face model are served by HireLucent itself
// (copied by scripts/face-guide-files.mjs), so no picture leaves the browser.
const WASM_PATH = '/mediapipe/wasm'
const MODEL_PATH = '/mediapipe/blaze_face_short_range.tflite'
const CHECK_MS = 120
const LIGHT_SIZE = 24

// The face's average light, from a small copy of that part of the picture.
function faceLight(video, face, canvas) {
  const context = canvas.getContext('2d', { willReadFrequently: true })
  const width = video.videoWidth
  const height = video.videoHeight
  context.drawImage(
    video,
    face.x * width,
    face.y * height,
    face.width * width,
    face.height * height,
    0,
    0,
    LIGHT_SIZE,
    LIGHT_SIZE,
  )
  const pixels = context.getImageData(0, 0, LIGHT_SIZE, LIGHT_SIZE).data
  let sum = 0
  for (let index = 0; index < pixels.length; index += 4) {
    sum += 0.299 * pixels[index] + 0.587 * pixels[index + 1] + 0.114 * pixels[index + 2]
  }
  return sum / (pixels.length / 4)
}

// MediaPipe's detections as shares of the picture.
function toFaces(detections, video) {
  return detections.map(({ boundingBox, keypoints = [] }) => ({
    x: boundingBox.originX / video.videoWidth,
    y: boundingBox.originY / video.videoHeight,
    width: boundingBox.width / video.videoWidth,
    height: boundingBox.height / video.videoHeight,
    eyes:
      keypoints.length > 2
        ? [
            [keypoints[0].x, keypoints[0].y],
            [keypoints[1].x, keypoints[1].y],
          ]
        : null,
    nose: keypoints.length > 2 ? [keypoints[2].x, keypoints[2].y] : null,
  }))
}

// Watches the camera picture about eight times a second and says which tip
// to show. status: "loading", "ready" or "unavailable" (no live tips; the
// photo is still checked on the server). greenSince: when the border last
// turned green, or null. faceRef: the face last found, for cutting out the
// photo.
export function useFaceGuide(videoRef, isOn) {
  const [status, setStatus] = useState('loading')
  const [tip, setTip] = useState('starting')
  const [greenSince, setGreenSince] = useState(null)
  const canvasRef = useRef(null)
  // The one face last found, with when it was found, for cutting out the
  // photo. Kept in a ref: it changes eight times a second and shows nothing.
  const faceRef = useRef(null)

  useEffect(() => {
    if (!isOn) return undefined
    let detector = null
    let timer = null
    let isCurrent = true

    async function start() {
      try {
        const { FaceDetector, FilesetResolver } = await import('@mediapipe/tasks-vision')
        const files = await FilesetResolver.forVisionTasks(WASM_PATH)
        detector = await FaceDetector.createFromOptions(files, {
          baseOptions: { modelAssetPath: MODEL_PATH },
          runningMode: 'VIDEO',
          minDetectionConfidence: 0.6,
        })
      } catch {
        if (isCurrent) setStatus('unavailable')
        return
      }
      if (!isCurrent) {
        detector.close()
        return
      }
      setStatus('ready')
      canvasRef.current = document.createElement('canvas')
      canvasRef.current.width = LIGHT_SIZE
      canvasRef.current.height = LIGHT_SIZE
      timer = setInterval(() => {
        const video = videoRef.current
        if (!video || video.readyState < 2 || !video.videoWidth) return
        const { detections } = detector.detectForVideo(video, performance.now())
        const faces = toFaces(detections, video)
        const light = faces.length === 1 ? faceLight(video, faces[0], canvasRef.current) : null
        const next = guideTip(faces, light)
        faceRef.current = faces.length === 1 ? { ...faces[0], foundAt: Date.now() } : null
        setTip(next)
        setGreenSince((since) => (next === 'good' ? (since ?? Date.now()) : null))
      }, CHECK_MS)
    }

    start()
    return () => {
      isCurrent = false
      clearInterval(timer)
      detector?.close()
      faceRef.current = null
    }
  }, [videoRef, isOn])

  return { status, tip: status === 'ready' ? tip : 'starting', greenSince, faceRef }
}
