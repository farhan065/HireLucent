// Wording for the stages of a job conversation, shared by several screens.
export const STAGE_LABELS = {
  describing: 'Describing the role',
  reviewing_description: 'Reviewing the description',
  confirming_requirements: 'Waiting for your approval',
  saved: 'Saved',
  confirming_post: 'Waiting for your approval',
  published: 'Published',
}

// Stages where the assistant is waiting for the interviewer to decide.
export const WAITING_STAGES = [
  'reviewing_description',
  'confirming_requirements',
  'confirming_post',
]

export const WEIGHT_LABELS = {
  technical_skills: 'Technical',
  experience: 'Experience',
  qualifications: 'Qualifications',
}

const LAST_THREAD_KEY = 'hirelucent_last_thread'

// The conversation used most recently, so the sidebar can reopen it.
export function getLastThread() {
  return sessionStorage.getItem(LAST_THREAD_KEY)
}

export function setLastThread(threadId) {
  if (threadId) sessionStorage.setItem(LAST_THREAD_KEY, threadId)
  else sessionStorage.removeItem(LAST_THREAD_KEY)
}
