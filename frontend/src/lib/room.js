// The live interview: opening its video room, letting the candidate in and
// ending it. Only the interviewer uses these; the candidate's pass for the
// room comes from lib/join.js.
import { apiRequest } from './api.js'

export function readInterview(sessionId) {
  return apiRequest(`/interviews/${sessionId}`)
}

// The interviewer's pass for the video room: { url, room, identity, token }.
export function openRoom(sessionId) {
  return apiRequest(`/interviews/${sessionId}/room`, { method: 'POST' })
}

export function admitCandidate(sessionId) {
  return apiRequest(`/interviews/${sessionId}/admit`, { method: 'POST' })
}

export function endInterview(sessionId) {
  return apiRequest(`/interviews/${sessionId}/end`, { method: 'POST' })
}

// "12:48": minutes and seconds since a moment.
export function elapsed(since, now = new Date()) {
  const seconds = Math.max(0, Math.floor((now - new Date(since)) / 1000))
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}
