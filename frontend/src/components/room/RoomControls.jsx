import { LogOut, Mic, MicOff, MonitorUp, MonitorX, PhoneOff, Video, VideoOff } from 'lucide-react'

const BASE =
  'inline-flex min-h-12.5 items-center gap-2 rounded-full px-5 font-display text-[15px] font-bold transition-colors disabled:opacity-50'
const PLAIN = `${BASE} border-[1.5px] border-line bg-white text-navy hover:bg-mist`
const OFF = `${BASE} border-[1.5px] border-danger/30 bg-danger-soft text-danger hover:bg-danger-soft/70`

// Mute, camera, share screen and the way out. Screen sharing has its own
// violet colour so it is easy to tell apart.
export default function RoomControls({ room, endLabel, isEnding = false, onEnd }) {
  const isConnected = room.state === 'connected'
  const EndIcon = endLabel.startsWith('Leave') ? LogOut : PhoneOff
  return (
    <div className="flex flex-wrap justify-center gap-3.5">
      <button
        type="button"
        onClick={room.toggleMicrophone}
        disabled={!isConnected}
        aria-pressed={!room.isMicrophoneOn}
        className={room.isMicrophoneOn ? PLAIN : OFF}
      >
        {room.isMicrophoneOn ? (
          <Mic className="size-4.5" aria-hidden="true" />
        ) : (
          <MicOff className="size-4.5" aria-hidden="true" />
        )}
        {room.isMicrophoneOn ? 'Mute' : 'Unmute'}
      </button>
      <button
        type="button"
        onClick={room.toggleCamera}
        disabled={!isConnected}
        aria-pressed={!room.isCameraOn}
        className={room.isCameraOn ? PLAIN : OFF}
      >
        {room.isCameraOn ? (
          <Video className="size-4.5" aria-hidden="true" />
        ) : (
          <VideoOff className="size-4.5" aria-hidden="true" />
        )}
        {room.isCameraOn ? 'Camera' : 'Camera off'}
      </button>
      <button
        type="button"
        onClick={room.toggleScreenShare}
        disabled={!isConnected || (Boolean(room.remoteScreen) && !room.isSharing)}
        aria-pressed={room.isSharing}
        title={room.remoteScreen && !room.isSharing ? 'The other person is sharing' : undefined}
        className={
          room.isSharing
            ? `${BASE} border-[1.5px] border-violet bg-violet text-white hover:opacity-90`
            : `${BASE} border-[1.5px] border-violet/30 bg-violet-soft text-violet hover:border-violet/60`
        }
      >
        {room.isSharing ? (
          <MonitorX className="size-4.5" aria-hidden="true" />
        ) : (
          <MonitorUp className="size-4.5" aria-hidden="true" />
        )}
        {room.isSharing ? 'Stop sharing' : 'Share screen'}
      </button>
      <button
        type="button"
        onClick={onEnd}
        disabled={isEnding}
        className={`${BASE} bg-danger text-white hover:opacity-90`}
      >
        <EndIcon className="size-4.5" aria-hidden="true" />
        {isEnding ? 'Ending…' : endLabel}
      </button>
    </div>
  )
}
