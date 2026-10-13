import { MessageSquareText, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useRoom } from '../../hooks/useRoom.js'
import { useUnread } from '../../hooks/useUnread.js'
import { elapsed, leaveFullScreen } from '../../lib/room.js'
import ConfirmDialog from '../ConfirmDialog.jsx'
import ConnectionChip from '../room/ConnectionChip.jsx'
import RoomControls from '../room/RoomControls.jsx'
import RoomMessages from '../room/RoomMessages.jsx'
import VideoStage from '../room/VideoStage.jsx'

// The candidate's interview room: the interviewer large in a standard-size
// frame, themselves small, and Mute, Camera, Share screen, Message and
// Leave. The video can go full screen. Message opens live messages with
// the interviewer beside the video (over it on a small screen); it is
// closed at first and counts unread messages. No transcript, notes or
// scores.
export default function CandidateRoom({ link, connection, renewPass, onLeft, onEnded }) {
  const room = useRoom(connection, renewPass)
  const [joinedAt] = useState(() => new Date())
  const [now, setNow] = useState(() => new Date())
  const [isConfirmingLeave, setIsConfirmingLeave] = useState(false)
  const [isMessageOpen, setIsMessageOpen] = useState(false)
  const [unread, markSeen] = useUnread(room.messages, isMessageOpen)

  function toggleMessages() {
    if (isMessageOpen) markSeen()
    setIsMessageOpen(!isMessageOpen)
  }

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // The interviewer ended the interview and its room was closed.
  useEffect(() => {
    if (room.endReason === 'ended') onEnded()
  }, [room.endReason, onEnded])

  return (
    <div className="flex min-h-screen flex-col bg-mist lg:h-screen">
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

      <main className="flex flex-1 gap-5 px-6 py-7 lg:min-h-0">
        <div className="flex min-w-0 flex-1 flex-col items-center gap-5">
          {room.notice && (
            <p className="w-full max-w-[65rem] rounded-2xl bg-amber-soft px-4 py-2.5 text-sm text-amber">
              {room.notice}
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
            renderControls={(place) => (
              <RoomControls
                room={room}
                endLabel="Leave"
                isOverlay={place === 'overlay'}
                message={
                  place === 'overlay'
                    ? null
                    : { isOpen: isMessageOpen, unread, onToggle: toggleMessages }
                }
                onEnd={() => {
                  leaveFullScreen()
                  setIsConfirmingLeave(true)
                }}
              />
            )}
          />
        </div>

        {isMessageOpen && (
          <aside
            aria-label="Messages with the interviewer"
            className="fixed inset-x-3 bottom-3 top-20 z-40 flex flex-col overflow-hidden rounded-card border border-line bg-white shadow-card lg:static lg:w-85 lg:shrink-0"
          >
            <header className="flex shrink-0 items-center justify-between gap-2 border-b border-line py-2.5 pl-4 pr-2.5">
              <h2 className="flex items-center gap-2 text-[15px] font-bold">
                <MessageSquareText className="size-4.5 text-brand" aria-hidden="true" />
                Message
              </h2>
              <button
                type="button"
                onClick={toggleMessages}
                aria-label="Close messages"
                className="flex size-9 items-center justify-center rounded-xl text-body hover:bg-mist"
              >
                <X className="size-4.5" aria-hidden="true" />
              </button>
            </header>
            <RoomMessages
              room={room}
              otherName="the interviewer"
              hint="Only you and the interviewer see these. They are not saved."
              waitingText="You can message the interviewer once they are in the room."
            />
          </aside>
        )}
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
