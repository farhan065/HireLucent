import { useEffect, useRef } from 'react'
import { Track } from 'livekit-client'

// Plays one LiveKit track: a labelled video tile, or hidden audio.
export default function TrackView({ track, label }) {
  const ref = useRef(null)

  useEffect(() => {
    const element = ref.current
    track.attach(element)
    return () => {
      track.detach(element)
    }
  }, [track])

  if (track.kind === Track.Kind.Audio) return <audio ref={ref} />

  return (
    <figure className="overflow-hidden rounded-card bg-navy shadow-card">
      <video ref={ref} muted playsInline className="aspect-video w-full object-cover" />
      <figcaption className="bg-white px-4 py-2.5 text-sm font-semibold text-navy">
        {label}
      </figcaption>
    </figure>
  )
}
