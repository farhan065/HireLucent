import { Wifi, WifiOff } from 'lucide-react'

const STATES = {
  connected: { label: 'Connected', className: 'bg-success-soft text-success', icon: Wifi },
  connecting: { label: 'Connecting…', className: 'bg-amber-soft text-amber', icon: Wifi },
  reconnecting: { label: 'Reconnecting…', className: 'bg-amber-soft text-amber', icon: Wifi },
  signalReconnecting: { label: 'Reconnecting…', className: 'bg-amber-soft text-amber', icon: Wifi },
  disconnected: { label: 'Disconnected', className: 'bg-danger-soft text-danger', icon: WifiOff },
}

// The video connection, in words and colour.
export default function ConnectionChip({ state }) {
  const { label, className, icon: Icon } = STATES[state] ?? STATES.connecting
  return (
    <span
      role="status"
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13.5px] font-semibold ${className}`}
    >
      <Icon className="size-4" aria-hidden="true" />
      {label}
    </span>
  )
}
