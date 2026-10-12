import { MicOff, MonitorUp, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import MediaTrack from './MediaTrack.jsx'

function initials(name) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join('') || '?'
  )
}

// A camera, or the person's initials when it is off.
function Feed({ track, name, isMirrored, isScreen, placeholder, size = 'large' }) {
  if (track) {
    return (
      <MediaTrack
        track={track}
        fit={isScreen ? 'contain' : 'cover'}
        isMirrored={isMirrored}
        label={isScreen ? `${name}'s screen` : `${name}'s camera`}
      />
    )
  }
  return (
    <div className="flex size-full flex-col items-center justify-center gap-3 text-white/80">
      <span
        className={`flex items-center justify-center rounded-full bg-white/10 font-display font-bold ${
          size === 'large' ? 'size-24 text-3xl' : 'size-12 text-base'
        }`}
      >
        {initials(name)}
      </span>
      {size === 'large' && <span className="text-[15px] font-semibold">{placeholder}</span>}
    </div>
  )
}

function Label({ children }) {
  return (
    <span className="flex items-center gap-2 rounded-xl bg-navy/70 px-3 py-1.5 text-sm font-semibold text-white">
      {children}
    </span>
  )
}

// The big video with a small floating tile at the bottom right, like a
// video call app. Clicking the tile swaps the two. A shared screen always
// takes the big view, with the other person's camera in the tile.
export default function VideoStage({ room, selfName, otherName, waitingText }) {
  const [isSwapped, setIsSwapped] = useState(false)
  const screen = room.remoteScreen ?? room.localScreen
  const screenOwner = room.remoteScreen ? otherName : selfName
  const self = { track: room.isCameraOn ? room.localCamera : null, name: selfName, isMirrored: true }
  const other = { track: room.remoteCamera, name: otherName, isMirrored: false }

  let main
  let tile
  if (screen) {
    main = { track: screen, name: screenOwner, isScreen: true }
    tile = room.remoteScreen ? self : other
  } else {
    main = isSwapped ? self : other
    tile = isSwapped ? other : self
  }
  const otherPlaceholder = room.isRemoteHere ? 'Camera off' : waitingText

  return (
    <div className="relative min-h-80 flex-1 overflow-hidden rounded-card bg-[#16233f]">
      <Feed
        {...main}
        placeholder={main === other ? otherPlaceholder : 'Camera off'}
      />
      <div className="absolute bottom-4 left-4 flex gap-2">
        <Label>
          {main.isScreen && <MonitorUp className="size-4" aria-hidden="true" />}
          {main === other && room.isRemoteMuted && <MicOff className="size-4" aria-hidden="true" />}
          {main.isScreen ? `${main.name} is sharing the screen` : main.name}
        </Label>
      </div>
      <button
        type="button"
        onClick={() => !screen && setIsSwapped((swapped) => !swapped)}
        aria-label={screen ? `${tile.name}'s camera` : 'Swap the two videos'}
        title={screen ? undefined : 'Swap the two videos'}
        className="absolute bottom-4 right-4 aspect-[16/10] w-56 max-w-[40%] overflow-hidden rounded-2xl border-2 border-white/70 bg-[#24345a] shadow-card"
      >
        <Feed {...tile} size="small" />
        <span className="absolute bottom-2 left-2 flex items-center gap-1.5 rounded-lg bg-navy/70 px-2 py-0.5 text-xs font-semibold text-white">
          {tile === other && room.isRemoteMuted && <MicOff className="size-3" aria-hidden="true" />}
          {tile === self ? 'You' : tile.name}
        </span>
        {!screen && (
          <RefreshCw
            className="absolute right-2 top-2 size-4 text-white/80"
            aria-hidden="true"
          />
        )}
      </button>
      {room.remoteAudio.map((audio) => (
        <MediaTrack key={audio.sid} track={audio} />
      ))}
    </div>
  )
}
