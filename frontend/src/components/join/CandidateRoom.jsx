import { useEffect, useState } from 'react'
import { useRoom } from '../../hooks/useRoom.js'
import { elapsed, leaveFullScreen } from '../../lib/room.js'
import ConfirmDialog from '../ConfirmDialog.jsx'
import ConnectionChip from '../room/ConnectionChip.jsx'
import RoomControls from '../room/RoomControls.jsx'
import VideoStage from '../room/VideoStage.jsx'

// The candidate's interview room: the interviewer large in a standard-size
// frame, themselves small, and Mute, Camera, Share screen and Leave. The
// video can go full screen. No transcript, notes or scores.
export default function CandidateRoom({ link, connection, onLeft, onEnded }) {
  const room = useRoom(connection)
  const [joinedAt] = useState(() => new Date())
  const [now, setNow] = useState(() => new Date())
  const [isConfirmingLeave, setIsConfirmingLeave] = useState(false)

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // The interviewer ended the interview and its room was closed.
  useEffect(() => {
    if (room.endReason === 'ended') onEnded()
  }, [room.endReason, onEnded])

  return (
    <div className="flex min-h-screen flex-col bg-mist">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-line bg-white px-6 py-3.5">
        <div className="flex items-center gap-4">
          <img src="/favicon.svg" alt="" className="size-8" />
          <div>
            <h1 className="text-lg font-extrabold tracking-tight">
              Interview for {link.job_title}
            </h1>
            <p className="text-[13.5px]">HireLucent hiring team</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-display text-base font-bold tabular-nums text-navy">
            {elapsed(joinedAt, now)}
          </span>
          <ConnectionChip state={room.state} />
        </div>
      </header>

      <main className="flex flex-1 flex-col items-center gap-5 px-6 py-7">
        {room.notice && (
          <p className="w-full max-w-[65rem] rounded-2xl bg-amber-soft px-4 py-2.5 text-sm text-amber">
            {room.notice}
          </p>
        )}
        {room.error && (
          <p
            role="alert"
            className="w-full max-w-[65rem] rounded-2xl bg-danger-soft px-4 py-2.5 text-sm font-semibold text-danger"
          >
            {room.error}
          </p>
        )}
        <VideoStage
          room={room}
          selfName="You"
          otherName={room.remoteName || 'Interviewer'}
          waitingText="Connecting to the interviewer…"
          heading={`Interview for ${link.job_title}`}
          clock={elapsed(joinedAt, now)}
          frameClassName="aspect-video max-w-[min(65rem,max(28rem,calc((100vh_-_11rem)*16/9)))]"
          showFullScreenLabel
          renderControls={(isOverlay) => (
            <RoomControls
              room={room}
              endLabel="Leave"
              isOverlay={isOverlay}
              onEnd={() => {
                leaveFullScreen()
                setIsConfirmingLeave(true)
              }}
            />
          )}
        />
      </main>

      {isConfirmingLeave && (
        <ConfirmDialog
          title="Leave the interview?"
          cancelLabel="Stay"
          confirmLabel="Leave"
          onConfirm={() => {
            room.leave()
            onLeft()
          }}
          onCancel={() => setIsConfirmingLeave(false)}
        >
          <p>
            The interview continues without you. You can come back with the link in your
            invitation while it is still going on.
          </p>
        </ConfirmDialog>
      )}
    </div>
  )
}
