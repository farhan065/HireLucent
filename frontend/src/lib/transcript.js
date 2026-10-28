// The transcript viewer of a finished interview: finding words in it and
// turning it into a text file to download. Everything here works on the
// turns already loaded, so nothing new is asked from the server.
import { dateValue, minutesBetween, shortDay, span } from './interviews.js'

function pad(value) {
  return String(value).padStart(2, '0')
}

// "00:12:38" from the milliseconds since the start, for the downloaded file.
export function stamp(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds % 60)}`
}

// The search as a pattern that ignores upper and lower case. Characters
// such as "." or "(" are searched for as they are.
function pattern(query) {
  const escaped = query.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return escaped ? new RegExp(escaped, 'gi') : null
}

// Every place the search appears, in the order spoken: the turn and where
// in its text the match starts.
export function findMatches(turns, query) {
  const regex = pattern(query)
  if (!regex) return []
  return turns.flatMap((turn) =>
    [...turn.text.matchAll(regex)].map((match) => ({
      turnId: turn.id,
      at: match.index,
      startMs: turn.start_ms,
    })),
  )
}

// A turn's text cut into plain pieces and matches, each piece with where it
// starts, so the current match can be told apart from the others.
export function splitText(text, query) {
  const regex = pattern(query)
  if (!regex) return [{ text, at: 0, isMatch: false }]
  const pieces = []
  let last = 0
  for (const match of text.matchAll(regex)) {
    if (match.index > last)
      pieces.push({ text: text.slice(last, match.index), at: last, isMatch: false })
    pieces.push({ text: match[0], at: match.index, isMatch: true })
    last = match.index + match[0].length
  }
  if (last < text.length) pieces.push({ text: text.slice(last), at: last, isMatch: false })
  return pieces
}

// How long the interview took, in milliseconds: from its start and end, or
// up to the last words if the end is missing.
export function lengthMs(interview, turns) {
  const lastWords = turns.reduce((latest, turn) => Math.max(latest, turn.end_ms), 0)
  if (!interview.started_at || !interview.ended_at) return lastWords
  return Math.max(new Date(interview.ended_at) - new Date(interview.started_at), lastWords)
}

// "Mon 13 Oct 2026, 2:00 – 2:47 PM", from when it really ran when known.
export function whenLabel(interview) {
  const start = interview.started_at ?? interview.scheduled_start
  const end = interview.ended_at ?? interview.scheduled_end
  return `${shortDay(start)} ${new Date(start).getFullYear()}, ${span(start, end)}`
}

// "took 47 min" once the interview has a start and an end.
export function tookLabel(interview) {
  if (!interview.started_at || !interview.ended_at) return ''
  return `took ${minutesBetween(interview.started_at, interview.ended_at)} min`
}

// "transcript_HL-BE-01_2026-10-13.txt". The candidate's name is left out of
// the file name, which shows up in download lists and email attachments.
export function fileName(info) {
  const code = info.job_code.replace(/[^A-Za-z0-9_-]+/g, '-')
  const day = new Date(info.interview.started_at ?? info.interview.scheduled_start)
  return `transcript_${code}_${dateValue(day)}.txt`
}

// The whole transcript as plain text: a short header, then one line per
// turn, "[00:12:38] Rakib: …".
export function fileText(info, turns) {
  const { interview } = info
  const firstName = interview.candidate_name.split(/\s+/)[0]
  const took = tookLabel(interview)
  const header = [
    'HireLucent · Interview transcript',
    `Candidate: ${interview.candidate_name}`,
    `Job: ${info.job_title} (${info.job_code})`,
    `Date: ${whenLabel(interview)}${took ? ` · ${took}` : ''}`,
  ]
  const lines = turns.map(
    (turn) =>
      `[${stamp(turn.start_ms)}] ${turn.speaker === 'interviewer' ? 'You' : firstName}: ${turn.text}`,
  )
  return `${[...header, '', ...lines].join('\n')}\n`
}

// Saves the text as a file in the browser's downloads. The mark at the
// start tells older editors that the file is UTF-8.
export function downloadText(name, text) {
  const url = URL.createObjectURL(new Blob(['﻿', text], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  // Freed a moment later, once the browser has started the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
