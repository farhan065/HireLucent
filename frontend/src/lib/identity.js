// The identity check of an interview (F7), for the interviewer only: how
// each result is labelled and what it asks the interviewer to do. The
// check never stops a candidate from joining.
import { Clock3, Info, ShieldAlert, ShieldCheck, TriangleAlert, Users } from 'lucide-react'
import { clock } from './interviews.js'

export const IDENTITY = {
  pending: {
    short: 'Waiting',
    long: 'Identity check after the PIN',
    tone: 'neutral',
    icon: Clock3,
  },
  verified: { short: 'Verified', long: 'Identity verified', tone: 'success', icon: ShieldCheck },
  low: {
    short: 'Low match',
    long: 'Low match: check identity',
    tone: 'warning',
    icon: TriangleAlert,
  },
  very_low: {
    short: 'Very low match',
    long: 'Very low match: verify identity',
    tone: 'danger',
    icon: ShieldAlert,
  },
  other_applicant: {
    short: 'Another applicant',
    long: 'Matches another applicant: verify identity',
    tone: 'danger',
    icon: Users,
  },
  not_checked: { short: 'Not checked', long: 'Identity not checked', tone: 'neutral', icon: Info },
}

export const IDENTITY_TONES = {
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
  neutral: 'bg-[#eef1f6] text-[#44526b]',
}

function score(value) {
  return value == null ? '' : value.toFixed(2)
}

const COMPARE = 'Compare the photo with the video before you start.'

// One short line under the label: what was found and what to do.
export function identityMessage(identity, hasPhoto) {
  switch (identity.result) {
    case 'pending':
      return 'Checked when the candidate joins.'
    case 'verified':
      return `Matches the application photo (${score(identity.score)}) · checked ${clock(identity.checked_at)}`
    case 'low':
      return `Only partly like the application photo (${score(identity.score)}). ${COMPARE}`
    case 'very_low':
      return `Does not look like the application photo (${score(identity.score)}). ${COMPARE}`
    case 'other_applicant':
      return `Looks more like ${identity.other_candidate_name ?? 'another applicant'} (${score(identity.other_score)}), another applicant for this job. Compare the photo with the video.`
    default:
      return `${identity.reason ?? 'No photo was compared.'} ${
        hasPhoto
          ? 'Compare the application photo with the video.'
          : 'Ask to see a photo ID if needed.'
      }`
  }
}

// The label once the candidate has taken (or skipped) the photo; nothing
// before that, except "Waiting" where asked for.
export function identityShown(identity) {
  return Boolean(identity) && identity.result !== 'pending'
}
