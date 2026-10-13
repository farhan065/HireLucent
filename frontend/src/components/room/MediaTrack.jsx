import { useEffect, useRef } from 'react'

// Plays one LiveKit track in a video or audio element. "fit" is "cover"
// for a camera and "contain" for a shared screen, so nothing is cut off.
export default function MediaTrack({ track, fit = 'cover', isMirrored = false, label }) {
  const ref = useRef(null)

  useEffect(() => {
    const element = ref.current
    track.attach(element)
    return () => {
      track.detach(element)
    }
  }, [track])

  if (track.kind === 'audio') return <audio ref={ref} />
  return (
    <video
      ref={ref}
      muted
      playsInline
      aria-label={label}
      className={`size-full ${fit === 'contain' ? 'object-contain' : 'object-cover'} ${
        isMirrored ? '-scale-x-100' : ''
      }`}
    />
  )
}
