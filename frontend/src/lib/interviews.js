// Shared helpers for interviews: the API calls, the scheduling rules and
// how times are shown. Times are stored in UTC. The Interviews tab shows them
// in the browser's time; cards from the AI Agent show them in the time zone
// the agent used, which they name.
import { apiRequest } from './api.js'

export const LENGTHS = [30, 45, 60]
export const BREAKS = [0, 15, 30]
export const MAX_DAYS_AHEAD = 60

export function scheduleInterviews(jobId, interviews) {
  return apiRequest(`/jobs/${jobId}/interviews`, { method: 'POST', body: { interviews } })
}

export function moveInterview(sessionId, start, end) {
  return apiRequest(`/interviews/${sessionId}`, { method: 'PUT', body: { start, end } })
}

export function cancelInterview(sessionId) {
  return apiRequest(`/interviews/${sessionId}/cancel`, { method: 'POST' })
}

// Only a cancelled interview can be deleted.
export function deleteInterview(sessionId) {
  return apiRequest(`/interviews/${sessionId}`, { method: 'DELETE' })
}

const MINUTE = 60 * 1000

export function addMinutes(date, minutes) {
  return new Date(date.getTime() + minutes * MINUTE)
}

export function minutesBetween(start, end) {
  return Math.round((new Date(end) - new Date(start)) / MINUTE)
}

// --- Date and time inputs (the browser's time) ---

function pad(value) {
  return String(value).padStart(2, '0')
}

// "2026-10-14" for a date input.
export function dateValue(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

// "15:00" for a time input.
export function timeValue(date) {
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

// The date and time inputs together, as a moment in the browser's time.
export function fromInputs(date, time) {
  if (!date || !time) return null
  const moment = new Date(`${date}T${time}`)
  return Number.isNaN(moment.getTime()) ? null : moment
}

// The earliest start the server accepts, rounded up to the next 5 minutes
// with a minute to spare, so the form can be filled in without hurrying.
export function earliestStart(rules, now = new Date()) {
  const earliest = addMinutes(now, (rules?.min_notice_minutes ?? 15) + 1)
  const step = 5 * MINUTE
  return new Date(Math.ceil(earliest.getTime() / step) * step)
}

// --- Showing times ---

function format(date, options, timeZone) {
  return new Date(date).toLocaleString('en-GB', { ...options, timeZone })
}

// "Tue 14 Oct". Browsers differ on the comma after the weekday.
export function shortDay(date, timeZone) {
  return format(date, { weekday: 'short', day: 'numeric', month: 'short' }, timeZone).replace(
    ',',
    '',
  )
}

// "Tuesday 14 October 2026"
export function longDay(date, timeZone) {
  const options = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }
  return format(date, options, timeZone).replace(',', '')
}

// "12 Oct"
export function formatShortDate(date) {
  return date ? format(date, { day: 'numeric', month: 'short' }) : ''
}

// "3:00 PM"
export function clock(date, timeZone) {
  return new Date(date).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    timeZone,
  })
}

// "3:00 – 3:45 PM", or "11:30 AM – 12:15 PM" across noon.
export function span(start, end, timeZone) {
  const from = clock(start, timeZone)
  const to = clock(end, timeZone)
  // Some browsers put a narrow space before AM and PM.
  const [fromTime, fromHalf] = from.split(/\s/)
  return to.endsWith(fromHalf) ? `${fromTime} – ${to}` : `${from} – ${to}`
}

// "3:45 PM" from "15:00" and 45 minutes, without any time zone.
export function clockAfter(time, minutes) {
  const [hours, mins] = time.split(':').map(Number)
  const total = (hours * 60 + mins + minutes) % (24 * 60)
  const hour = Math.floor(total / 60)
  return `${hour % 12 || 12}:${pad(total % 60)} ${hour < 12 ? 'AM' : 'PM'}`
}

function isSameDay(a, b) {
  return dateValue(new Date(a)) === dateValue(new Date(b))
}

// "Today, Tue 14 Oct" or "Wed 15 Oct", in the browser's time.
export function dayLabel(date, now = new Date()) {
  const day = shortDay(date)
  return isSameDay(date, now) ? `Today, ${day}` : day
}

// The browser's time zone as people read it, for example "Dhaka, GMT+6".
export function browserZoneLabel(now = new Date()) {
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone ?? ''
  const city = zone.split('/').at(-1)?.replace(/_/g, ' ') || 'Local time'
  const offset = -now.getTimezoneOffset()
  const hours = Math.floor(Math.abs(offset) / 60)
  const rest = Math.abs(offset) % 60
  return `${city}, GMT${offset >= 0 ? '+' : '-'}${hours}${rest ? `:${pad(rest)}` : ''}`
}

// --- An interview's state ---

const ACTIVE = ['scheduled', 'in_progress']

export function isActive(interview) {
  return ACTIVE.includes(interview.status)
}

// When the room can be entered: "too_early", "open", "missed" or "closed".
export function joinState(interview, rules, now = new Date()) {
  if (interview.status === 'in_progress') return 'open'
  if (interview.status !== 'scheduled') return 'closed'
  const opens = addMinutes(new Date(interview.scheduled_start), -(rules?.join_opens_minutes_before ?? 10))
  if (now < opens) return 'too_early'
  if (now > new Date(interview.scheduled_end)) return 'missed'
  return 'open'
}

// When the Start button opens: "3:50 PM" today, otherwise "15 Oct".
export function opensLabel(interview, rules, now = new Date()) {
  const opens = addMinutes(new Date(interview.scheduled_start), -(rules?.join_opens_minutes_before ?? 10))
  return isSameDay(opens, now) ? clock(opens) : formatShortDate(opens)
}

// Interviews that have not ended and start today, for the tab's badge.
export function countToday(interviews, now = new Date()) {
  return (interviews ?? []).filter(
    (item) => isActive(item) && isSameDay(item.scheduled_start, now),
  ).length
}

// Upcoming interviews first, then finished ones, newest first, then
// cancelled ones.
export function sortInterviews(interviews) {
  const group = (item) => (isActive(item) ? 0 : item.status === 'completed' ? 1 : 2)
  return [...interviews].sort((a, b) => {
    if (group(a) !== group(b)) return group(a) - group(b)
    const order = new Date(a.scheduled_start) - new Date(b.scheduled_start)
    return group(a) === 0 ? order : -order
  })
}

// "1 interview invite" or "3 interview invites".
export function invites(count) {
  return `${count} interview ${count === 1 ? 'invite' : 'invites'}`
}

// "Final score 86"
export function scoreLabel(score) {
  return score == null ? 'Not scored' : `Final score ${Math.round(score)}`
}

// "Tue 14 Oct · 3:00 – 3:45 PM", in the given time zone.
export function rangeLabel(start, end, timeZone) {
  if (!start || !end) return ''
  return `${shortDay(start, timeZone)} · ${span(start, end, timeZone)}`
}

// How an interview card from the AI Agent is marked.
export const CARD_STATUS = {
  waiting: { tone: 'info', label: 'Waiting for your approval' },
  approved: { tone: 'success', label: 'Approved by you' },
  changed: { tone: 'neutral', label: 'Changed' },
}
