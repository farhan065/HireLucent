import { Check } from 'lucide-react'

function Chip({ isOk, okText, waitText }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13.5px] font-semibold ${
        isOk ? 'bg-success-soft text-success' : 'bg-white text-body ring-1 ring-line'
      }`}
    >
      {isOk && <Check className="size-3.5" aria-hidden="true" />}
      {isOk ? okText : waitText}
    </span>
  )
}

// Only what this page can really check: the camera gives a picture and the
// microphone has heard a sound.
export default function DeviceChecks({ preview }) {
  return (
    <div className="flex flex-wrap gap-2.5" aria-live="polite">
      <Chip isOk={preview.cameraWorks} okText="Camera working" waitText="Camera not on" />
      <Chip
        isOk={preview.microphoneWorks}
        okText="Microphone working"
        waitText={preview.hasMicrophone ? 'Say something to test your microphone' : 'No microphone'}
      />
    </div>
  )
}
