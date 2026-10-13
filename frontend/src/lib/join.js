// The candidate's private interview link. The token from the link is sent
// in the request body, never in an address, so it is not logged. No
// interviewer sign-in is ever sent from these pages.
import { apiRequest } from './api.js'

export function readLink(token) {
  return apiRequest('/join/info', { method: 'POST', body: { token }, auth: null })
}

// Returns the candidate's pass for this one interview.
export async function enterWaitingRoom(token) {
  const { access_token: pass } = await apiRequest('/join/enter', {
    method: 'POST',
    body: { token, consent: true },
    auth: null,
  })
  return pass
}

// "waiting", "started" or "ended".
export async function checkIn(pass) {
  const { state } = await apiRequest('/join/status', { auth: pass })
  return state
}

export function leaveWaitingRoom(pass) {
  return apiRequest('/join/leave', { method: 'POST', auth: pass })
}

// "in 1 h 12 min", "in 4 min" or "now".
export function timeUntil(date, now = new Date()) {
  const minutes = Math.ceil((new Date(date) - now) / 60000)
  if (minutes <= 0) return 'now'
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours === 0) return `in ${minutes} min`
  return rest === 0 ? `in ${hours} h` : `in ${hours} h ${rest} min`
}

// The candidate's pass for the video room, given once they were let in.
export function joinRoom(pass) {
  return apiRequest('/join/room', { method: 'POST', auth: pass })
}
