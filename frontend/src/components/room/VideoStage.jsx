import { Maximize, MicOff, Minimize, MonitorUp, RefreshCw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import ConnectionOverlay, { RemoteDropped } from './ConnectionOverlay.jsx'
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

// "Nadia Karim's" and "Nadia Karim", or "The interviewer's" and "the
// interviewer" when the other person is the interviewer.
function droppedName(name) {
  if (name === 'Interviewer') return { title: "The interviewer's", waiting: 'the interviewer' }
  return { title: `${name}'s`, waiting: name }
}

function Label({ children }) {
  return (
    <span className="flex items-center gap-2 rounded-xl bg-navy/70 px-3 py-1.5 text-sm font-semibold text-white">
      {children}
    </span>
  )
}

// Follows whether this element is shown full screen. Esc leaves full
// screen too; the browser handles that and the state follows.
function useFullScreen(ref) {
  const [isFullScreen, setIsFullScreen] = useState(false)
  useEffect(() => {
    function handleChange() {
      setIsFullScreen(Boolean(ref.current) && document.fullscreenElement === ref.current)
    }
    document.addEventListener('fullscreenchange', handleChange)
    return () => document.removeEventListener('fullscreenchange', handleChange)
  }, [ref])
  return isFullScreen
}

// The video in a frame sized by the page, with the controls below it. The big
// video has a small floating tile at the bottom right, like a video call
// app; clicking the tile swaps the two. A shared screen always takes the
// big view, with the other person's camera in the tile. Full screen shows
// the video on the whole screen with the controls floating over it.
export default function VideoStage({
  room,
  selfName,
  otherName,
  waitingText,
  heading,
  clock,
  frameClassName = '',
  showFullScreenLabel = false,
  renderControls,
}) {
  const stageRef = useRef(null)
  const isFullScreen = useFullScreen(stageRef)
  const [isSwapped, setIsSwapped] = useState(false)
  const canFullScreen = Boolean(document.fullscreenEnabled)

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
  // The other person dropped while this person is still connected.
  const isOtherDropped = Boolean(room.remoteLostAt) && !room.lostAt && !room.isReplaced

  function toggleFullScreen() {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => null)
    else stageRef.current?.requestFullscreen().catch(() => null)
  }

  return (
    <div
      ref={stageRef}
      className={isFullScreen ? 'relative h-screen w-screen bg-[#0b1428]' : 'flex w-full flex-col gap-3.5'}
    >
      <div
        className={
          isFullScreen
            ? 'absolute inset-0 overflow-hidden bg-[#16233f]'
            : `relative mx-auto w-full shrink-0 overflow-hidden rounded-card bg-[#16233f] shadow-[0_14px_34px_rgb(11_31_75/0.12)] ${frameClassName}`
        }
      >
        {main === other && isOtherDropped ? (
          <RemoteDropped
            name={droppedName(otherName)}
            initials={initials(otherName)}
            since={room.remoteLostAt}
          />
        ) : (
          <Feed {...main} placeholder={main === other ? otherPlaceholder : 'Camera off'} />
        )}

        {isFullScreen ? (
          <div className="absolute inset-x-6 top-5 flex items-center justify-between gap-4">
            <span className="rounded-xl bg-[#0b1428]/60 px-3.5 py-2 text-[15px] font-semibold text-white">
              {heading}
            </span>
            <div className="flex items-center gap-2.5">
              {clock && (
                <span className="rounded-xl bg-[#0b1428]/60 px-3 py-2 font-display text-[15px] font-bold tabular-nums text-white">
                  {clock}
                </span>
              )}
              <button
                type="button"
                onClick={toggleFullScreen}
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-white/90 px-3.5 text-sm font-bold text-navy hover:bg-white"
              >
                <Minimize className="size-4" aria-hidden="true" />
                Exit full screen
              </button>
            </div>
          </div>
        ) : (
          canFullScreen && (
            <button
              type="button"
              onClick={toggleFullScreen}
              aria-label="Full screen"
              title="Full screen"
              className={`absolute right-3.5 top-3.5 inline-flex min-h-10 min-w-10 items-center justify-center gap-2 rounded-xl bg-navy/70 text-sm font-semibold text-white hover:bg-navy/85 ${
                showFullScreenLabel ? 'px-3.5' : ''
              }`}
            >
              <Maximize className="size-4.5" aria-hidden="true" />
              {showFullScreenLabel && 'Full screen'}
            </button>
          )
        )}

        {isFullScreen && room.notice && (
          <p className="absolute left-1/2 top-20 -translate-x-1/2 rounded-2xl bg-amber-soft px-4 py-2.5 text-sm text-amber">
            {room.notice}
          </p>
        )}

        <div className={`absolute flex gap-2 ${isFullScreen ? 'bottom-28 left-6' : 'bottom-3.5 left-3.5'}`}>
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
          className={`absolute aspect-[16/10] overflow-hidden rounded-2xl border-2 border-white/80 bg-[#24345a] shadow-card ${
            isFullScreen ? 'bottom-28 right-6 w-64' : 'bottom-3.5 right-3.5 w-[24%] min-w-28 max-w-56'
          }`}
        >
          <Feed {...tile} size="small" />
          <span className="absolute bottom-2 left-2 flex items-center gap-1.5 rounded-lg bg-navy/70 px-2 py-0.5 text-xs font-semibold text-white">
            {tile === other && room.isRemoteMuted && <MicOff className="size-3" aria-hidden="true" />}
            {tile === self ? 'You' : tile.name}
          </span>
          {!screen && (
            <RefreshCw className="absolute right-2 top-2 size-4 text-white/80" aria-hidden="true" />
          )}
        </button>
        {room.remoteAudio.map((audio) => (
          <MediaTrack key={audio.sid} track={audio} />
        ))}
        <ConnectionOverlay room={room} />
      </div>

      <div className={isFullScreen ? 'absolute inset-x-0 bottom-6 flex justify-center' : ''}>
        {renderControls(isFullScreen)}
      </div>
    </div>
  )
}
