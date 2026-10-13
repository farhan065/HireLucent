import {
  LogOut,
  MessageSquareText,
  Mic,
  MicOff,
  MonitorUp,
  MonitorX,
  PhoneOff,
  Video,
  VideoOff,
} from 'lucide-react'

const BASE =
  'inline-flex min-h-10 items-center gap-1.75 rounded-full px-4 font-display text-[13.5px] font-bold transition-colors disabled:opacity-50'
const PLAIN = `${BASE} border-[1.5px] border-line bg-white text-navy hover:bg-mist`
// Over the video in full screen.
const GLASS = `${BASE} border-[1.5px] border-transparent bg-white/15 text-white hover:bg-white/25`
const OFF = `${BASE} border-[1.5px] border-danger/30 bg-danger-soft text-danger hover:bg-danger-soft/70`

// Small, icon-only buttons inside the video frame, the size of the name
// label beside them. Each one names itself on hover.
const SMALL =
  'inline-flex h-8 items-center justify-center rounded-[10px] text-white transition-colors disabled:opacity-50'
const SMALL_ICON = `${SMALL} w-8 bg-navy/70 hover:bg-navy/85`
const SMALL_OFF = `${SMALL} w-8 bg-danger hover:opacity-90`

function Unread({ count }) {
  if (!count) return null
  return (
    <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-danger px-1.5 font-sans text-xs font-bold text-white">
      {count}
    </span>
  )
}

function CompactControls({ room, endLabel, isEnding, onEnd }) {
  const isConnected = room.state === 'connected'
  const EndIcon = endLabel.startsWith('Leave') ? LogOut : PhoneOff
  const microphoneLabel = room.isMicrophoneOn ? 'Mute' : 'Unmute'
  const cameraLabel = room.isCameraOn ? 'Turn camera off' : 'Turn camera on'
  const isShareBlocked = Boolean(room.remoteScreen) && !room.isSharing
  const shareLabel = room.isSharing
    ? 'Stop sharing'
    : isShareBlocked
      ? 'The other person is sharing'
      : 'Share screen'
  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        onClick={room.toggleMicrophone}
        disabled={!isConnected}
        aria-pressed={!room.isMicrophoneOn}
        aria-label={microphoneLabel}
        title={microphoneLabel}
        className={room.isMicrophoneOn ? SMALL_ICON : SMALL_OFF}
      >
        {room.isMicrophoneOn ? (
          <Mic className="size-4" aria-hidden="true" />
        ) : (
          <MicOff className="size-4" aria-hidden="true" />
        )}
      </button>
      <button
        type="button"
        onClick={room.toggleCamera}
        disabled={!isConnected}
        aria-pressed={!room.isCameraOn}
        aria-label={cameraLabel}
        title={cameraLabel}
        className={room.isCameraOn ? SMALL_ICON : SMALL_OFF}
      >
        {room.isCameraOn ? (
          <Video className="size-4" aria-hidden="true" />
        ) : (
          <VideoOff className="size-4" aria-hidden="true" />
        )}
      </button>
      <button
        type="button"
        onClick={room.toggleScreenShare}
        disabled={!isConnected || isShareBlocked}
        aria-pressed={room.isSharing}
        aria-label={shareLabel}
        title={shareLabel}
        className={`${SMALL} w-8 ${
          room.isSharing ? 'bg-violet ring-2 ring-white/70' : 'bg-violet/85 hover:bg-violet'
        }`}
      >
        {room.isSharing ? (
          <MonitorX className="size-4" aria-hidden="true" />
        ) : (
          <MonitorUp className="size-4" aria-hidden="true" />
        )}
      </button>
      <button
        type="button"
        onClick={onEnd}
        disabled={isEnding}
        aria-label={endLabel}
        title={endLabel}
        className={`${SMALL} gap-1.5 bg-[#d92d20] px-3 font-display text-[12.5px] font-bold hover:opacity-90`}
      >
        <EndIcon className="size-4" aria-hidden="true" />
        {isEnding ? 'Ending…' : endLabel.split(' ')[0]}
      </button>
    </div>
  )
}

// Mute, camera, share screen and the way out. Screen sharing has its own
// violet colour so it is easy to tell apart. "variant":
//   "full"    labelled buttons below the video, or over it in full screen
//   "compact" small icon buttons inside the video frame
// The candidate also gets a Message button with the number of unread
// messages.
export default function RoomControls({
  room,
  endLabel,
  isEnding = false,
  isOverlay = false,
  variant = 'full',
  onEnd,
  message,
}) {
  if (variant === 'compact') {
    return <CompactControls room={room} endLabel={endLabel} isEnding={isEnding} onEnd={onEnd} />
  }
  const isConnected = room.state === 'connected'
  const EndIcon = endLabel.startsWith('Leave') ? LogOut : PhoneOff
  const plain = isOverlay ? GLASS : PLAIN
  return (
    <div
      className={`flex flex-wrap justify-center gap-2.5 ${
        isOverlay ? 'rounded-full bg-[#0b1428]/75 p-2' : ''
      }`}
    >
      <button
        type="button"
        onClick={room.toggleMicrophone}
        disabled={!isConnected}
        aria-pressed={!room.isMicrophoneOn}
        className={room.isMicrophoneOn ? plain : OFF}
      >
        {room.isMicrophoneOn ? (
          <Mic className="size-4" aria-hidden="true" />
        ) : (
          <MicOff className="size-4" aria-hidden="true" />
        )}
        {room.isMicrophoneOn ? 'Mute' : 'Unmute'}
      </button>
      <button
        type="button"
        onClick={room.toggleCamera}
        disabled={!isConnected}
        aria-pressed={!room.isCameraOn}
        className={room.isCameraOn ? plain : OFF}
      >
        {room.isCameraOn ? (
          <Video className="size-4" aria-hidden="true" />
        ) : (
          <VideoOff className="size-4" aria-hidden="true" />
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
            : isOverlay
              ? GLASS
              : `${BASE} border-[1.5px] border-violet/30 bg-violet-soft text-violet hover:border-violet/60`
        }
      >
        {room.isSharing ? (
          <MonitorX className="size-4" aria-hidden="true" />
        ) : (
          <MonitorUp className="size-4" aria-hidden="true" />
        )}
        {room.isSharing ? 'Stop sharing' : 'Share screen'}
      </button>
      {message && (
        <button
          type="button"
          onClick={message.onToggle}
          aria-pressed={message.isOpen}
          aria-label={message.unread ? `Message, ${message.unread} unread` : 'Message'}
          className={
            message.isOpen
              ? `${BASE} border-[1.5px] border-brand bg-tint text-brand`
              : plain
          }
        >
          <MessageSquareText className="size-4" aria-hidden="true" />
          Message
          <Unread count={message.unread} />
        </button>
      )}
      <button
        type="button"
        onClick={onEnd}
        disabled={isEnding}
        className={`${BASE} bg-danger text-white hover:opacity-90`}
      >
        <EndIcon className="size-4" aria-hidden="true" />
        {isEnding ? 'Ending…' : endLabel}
      </button>
    </div>
  )
}
