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

// Questions the AI suggested for the candidate, oldest first.
export function readQuestions(sessionId) {
  return apiRequest(`/interviews/${sessionId}/questions`)
}

// Five more suggested questions; returns all of them.
export function suggestQuestions(sessionId) {
  return apiRequest(`/interviews/${sessionId}/questions`, { method: 'POST' })
}

export function markAsked(sessionId, questionId, asked) {
  return apiRequest(`/interviews/${sessionId}/questions/${questionId}`, {
    method: 'PATCH',
    body: { asked },
  })
}

// Every turn of the interview transcript saved so far, oldest first.
export function readTranscript(sessionId) {
  return apiRequest(`/interviews/${sessionId}/transcript`)
}

// The room's read-only chat with the AI Agent.
export function readChat(sessionId) {
  return apiRequest(`/interviews/${sessionId}/chat`)
}

export function sendChat(sessionId, message) {
  return apiRequest(`/interviews/${sessionId}/chat`, { method: 'POST', body: { message } })
}

// Back from full screen, so a dialog opened next can be seen.
export function leaveFullScreen() {
  if (document.fullscreenElement) document.exitFullscreen().catch(() => null)
}

// "12:48": minutes and seconds since a moment.
export function elapsed(since, now = new Date()) {
  const seconds = Math.max(0, Math.floor((now - new Date(since)) / 1000))
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}

// "12:31" or "1:02:05": a time in milliseconds from the start of the
// interview, as the transcript shows it.
export function fromStart(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = String(seconds % 60).padStart(2, '0')
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`
}
