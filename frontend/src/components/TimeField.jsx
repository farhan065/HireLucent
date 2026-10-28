// A time picker in the 12-hour clock: hour, minute and AM/PM side by side.
// The browser's own time box follows the computer's region setting, which
// may be the 24-hour clock, so it is not used. The value going in and out
// is still "HH:MM" in the 24-hour clock, as the server takes it.

const HOURS = Array.from({ length: 12 }, (_, index) => index + 1)
const MINUTE_STEP = 5
const STEP_MINUTES = Array.from({ length: 60 / MINUTE_STEP }, (_, index) => index * MINUTE_STEP)
const SELECT = 'cursor-pointer bg-transparent py-1 text-navy focus:outline-none'

const pad = (number) => String(number).padStart(2, '0')

// "23:05" → { hour: 11, minute: 5, period: 'PM' }
function split(value) {
  const [hours, minutes] = (value || '09:00').split(':').map(Number)
  return {
    hour: hours % 12 || 12,
    minute: minutes || 0,
    period: hours >= 12 ? 'PM' : 'AM',
  }
}

// { hour: 11, minute: 5, period: 'PM' } → "23:05"
function join({ hour, minute, period }) {
  const hours = (hour % 12) + (period === 'PM' ? 12 : 0)
  return `${pad(hours)}:${pad(minute)}`
}

export default function TimeField({ value, onChange, label, className = '' }) {
  const parts = split(value)
  // A start time such as 10:07 that is not on the 5-minute steps stays
  // selectable until it is changed.
  const minutes = STEP_MINUTES.includes(parts.minute)
    ? STEP_MINUTES
    : [...STEP_MINUTES, parts.minute].sort((a, b) => a - b)

  function change(changes) {
    onChange(join({ ...parts, ...changes }))
  }

  return (
    <div
      role="group"
      aria-label={label}
      className={`flex items-center gap-0.5 focus-within:border-brand ${className}`}
    >
      <select
        aria-label={`${label}: hour`}
        value={parts.hour}
        onChange={(event) => change({ hour: Number(event.target.value) })}
        className={`${SELECT} w-11`}
      >
        {HOURS.map((hour) => (
          <option key={hour} value={hour}>
            {hour}
          </option>
        ))}
      </select>
      <span aria-hidden="true">:</span>
      <select
        aria-label={`${label}: minutes`}
        value={parts.minute}
        onChange={(event) => change({ minute: Number(event.target.value) })}
        className={`${SELECT} w-11`}
      >
        {minutes.map((minute) => (
          <option key={minute} value={minute}>
            {pad(minute)}
          </option>
        ))}
      </select>
      <select
        aria-label={`${label}: AM or PM`}
        value={parts.period}
        onChange={(event) => change({ period: event.target.value })}
        className={`${SELECT} ml-auto w-13 font-semibold`}
      >
        <option value="AM">AM</option>
        <option value="PM">PM</option>
      </select>
    </div>
  )
}
