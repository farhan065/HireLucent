// The candidate's private interview link. The token from the link is sent
// in the request body, never in an address, so it is not logged. No
// interviewer sign-in is ever sent from these pages.
import { apiRequest } from './api.js'

export function readLink(token) {
  return apiRequest('/join/info', { method: 'POST', body: { token }, auth: null })
}

// The interview PIN from the invitation: { result: "ok" | "wrong" |
// "locked", tries_left, locked_until }.
export function checkPin(token, pin) {
  return apiRequest('/join/pin', { method: 'POST', body: { token, pin }, auth: null })
}

// Returns the candidate's pass for this one interview, and whether the
// identity photo is still to be taken.
export async function enterWaitingRoom(token, pin = null) {
  const { access_token: pass, photo_needed: photoNeeded } = await apiRequest('/join/enter', {
    method: 'POST',
    body: pin ? { token, consent: true, pin } : { token, consent: true },
    auth: null,
  })
  return { pass, photoNeeded }
}

// The one identity photo: { state: "done" | "retry", tries_left }. The
// candidate is never told how well it matched.
export function sendIdentityPhoto(pass, photo) {
  const body = new FormData()
  body.append('photo', photo, 'photo.jpg')
  return apiRequest('/join/identity', { method: 'POST', body, auth: pass })
}

// Join without the photo: "no_camera" or "gave_up".
export function skipIdentityPhoto(pass, reason) {
  return apiRequest('/join/identity/skip', { method: 'POST', body: { reason }, auth: pass })
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
