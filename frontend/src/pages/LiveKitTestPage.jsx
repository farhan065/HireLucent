import { Track } from 'livekit-client'
import Button from '../components/Button.jsx'
import StatusChip from '../components/StatusChip.jsx'
import TrackView from '../components/video/TrackView.jsx'
import { useTestRoom } from '../hooks/useTestRoom.js'

const STATE_TONES = {
  connected: 'success',
  connecting: 'info',
  reconnecting: 'warning',
  signalReconnecting: 'warning',
  disconnected: 'neutral',
}

// Temporary page that checks the video server with two browser tabs.
// It is removed when the interview room is built.
export default function LiveKitTestPage() {
  const { state, tracks, notice, error, join, leave } = useTestRoom()
  const videos = tracks.filter(({ track }) => track.kind === Track.Kind.Video)
  // Only the other tab's audio is played, so a tab never hears itself.
  const sounds = tracks.filter(({ track, isLocal }) => !isLocal && track.kind === Track.Kind.Audio)
  const inRoom = state !== 'disconnected'

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">Video test</h1>
          <p className="mt-1.5 max-w-2xl text-base">
            Open this page in two tabs and join in both. Each tab should see and hear the other.
            Use headphones to avoid echo.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusChip tone={STATE_TONES[state] ?? 'neutral'}>{state}</StatusChip>
          {inRoom ? (
            <Button variant="outline" onClick={leave}>
              Leave
            </Button>
          ) : (
            <Button onClick={join}>Join test room</Button>
          )}
        </div>
      </header>

      {error && (
        <p role="alert" className="font-semibold text-danger">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="rounded-2xl bg-warning-soft px-4 py-3.5 text-sm text-warning">
          {notice}
        </p>
      )}

      <div className="grid gap-5 md:grid-cols-2">
        {videos.map(({ track, identity, isLocal }) => (
          <TrackView key={track.sid ?? identity} track={track} label={isLocal ? 'You' : identity} />
        ))}
      </div>
      {sounds.map(({ track, identity }) => (
        <TrackView key={track.sid ?? identity} track={track} />
      ))}
    </div>
  )
}
