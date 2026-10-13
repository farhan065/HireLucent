import { Mic, MicOff, Video, VideoOff } from 'lucide-react'
import { useEffect, useRef } from 'react'

const SELECT =
  'min-h-11.5 min-w-0 flex-1 basis-48 rounded-xl border-[1.5px] border-line bg-white px-3 text-[14.5px] text-navy focus:border-brand focus:outline-none'

// Five bars that light up with the microphone level.
function LevelBars({ level }) {
  const lit = Math.round(level * 5)
  return (
    <span aria-hidden="true" className="flex h-4 items-end gap-[3px]">
      {[6, 11, 15, 9, 13].map((height, index) => (
        <span
          key={height}
          style={{ height }}
          className={`w-1 rounded-sm ${index < lit ? 'bg-[#6ee7b7]' : 'bg-white/35'}`}
        />
      ))}
    </span>
  )
}

function RoundButton({ isOn, onLabel, offLabel, OnIcon, OffIcon, onClick }) {
  return (
    <button
      type="button"
      aria-label={isOn ? onLabel : offLabel}
      aria-pressed={!isOn}
      onClick={onClick}
      className={`flex size-12.5 shrink-0 items-center justify-center rounded-full border-[1.5px] ${
        isOn
          ? 'border-line bg-white text-navy hover:bg-mist'
          : 'border-danger bg-danger text-white hover:opacity-90'
      }`}
    >
      {isOn ? <OnIcon className="size-5" aria-hidden="true" /> : <OffIcon className="size-5" aria-hidden="true" />}
    </button>
  )
}

// The candidate's camera preview with its controls. "showSelects" adds the
// camera and microphone lists, used before joining.
export default function DevicePreview({ preview, showSelects = false, note }) {
  const { devices, stream } = preview
  const videoRef = useRef(null)

  // Show the camera in the preview.
  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = stream
  }, [stream])

  return (
    <section aria-label="Your camera and microphone" className="flex min-w-0 flex-col gap-3.5">
      <div className="relative aspect-[16/10] w-full overflow-hidden rounded-card bg-[#16233f]">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          aria-label="Your camera preview"
          className={`size-full -scale-x-100 object-cover ${preview.cameraOn ? '' : 'invisible'}`}
        />
        {!preview.cameraOn && (
          <p className="absolute inset-0 flex items-center justify-center text-[15px] font-semibold text-white/80">
            Camera off
          </p>
        )}
        {preview.error && (
          <p
            role="alert"
            className="absolute inset-x-6 top-1/2 -translate-y-1/2 rounded-2xl bg-white/95 px-4 py-3 text-center text-sm font-semibold text-danger"
          >
            {preview.error}
          </p>
        )}
        <div className="absolute bottom-4 left-4 flex items-center gap-2.5 rounded-xl bg-navy/70 px-3 py-2 text-sm font-semibold text-white">
          {preview.microphoneOn ? (
            <Mic className="size-4" aria-hidden="true" />
          ) : (
            <MicOff className="size-4" aria-hidden="true" />
          )}
          <LevelBars level={preview.level} />
          You
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <RoundButton
          isOn={preview.microphoneOn}
          onLabel="Turn microphone off"
          offLabel="Turn microphone on"
          OnIcon={Mic}
          OffIcon={MicOff}
          onClick={preview.toggleMicrophone}
        />
        <RoundButton
          isOn={preview.cameraOn}
          onLabel="Turn camera off"
          offLabel="Turn camera on"
          OnIcon={Video}
          OffIcon={VideoOff}
          onClick={preview.toggleCamera}
        />
        {showSelects ? (
          <>
            <label className="sr-only" htmlFor="camera-choice">
              Camera
            </label>
            <select
              id="camera-choice"
              value={preview.cameraId}
              onChange={(event) => preview.setCameraId(event.target.value)}
              className={SELECT}
            >
              {devices.cameras.map((device, index) => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.label || `Camera ${index + 1}`}
                </option>
              ))}
            </select>
            <label className="sr-only" htmlFor="microphone-choice">
              Microphone
            </label>
            <select
              id="microphone-choice"
              value={preview.microphoneId}
              onChange={(event) => preview.setMicrophoneId(event.target.value)}
              className={SELECT}
            >
              {devices.microphones.map((device, index) => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.label || `Microphone ${index + 1}`}
                </option>
              ))}
            </select>
          </>
        ) : (
          note && <span className="text-sm">{note}</span>
        )}
      </div>
    </section>
  )
}
