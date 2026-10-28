// Grouping the Screening tab's candidates by their result, for the Show
// filter. Each candidate is in exactly one group, so the counts add up.

export const RESULT_GROUPS = [
  { key: 'all', label: 'All candidates', dot: 'bg-brand' },
  { key: 'shortlisted', label: 'Shortlisted', dot: 'bg-teal' },
  { key: 'scored', label: 'Scored', dot: 'bg-success' },
  { key: 'excluded', label: 'Excluded', dot: 'bg-warning' },
  { key: 'failed', label: 'Could not be read', dot: 'bg-danger' },
  // Read but not scored yet, for example after a run was stopped. Offered
  // only when someone is in it.
  { key: 'unfinished', label: 'Not finished', dot: 'bg-body', isOptional: true },
]

export function resultGroup(candidate) {
  if (candidate.status === 'shortlisted') return 'shortlisted'
  if (candidate.status === 'excluded') return 'excluded'
  if (candidate.status === 'screening_failed') return 'failed'
  if (candidate.scores) return 'scored'
  return 'unfinished'
}

// How many candidates are in each group, plus "all".
export function countGroups(candidates) {
  const counts = Object.fromEntries(RESULT_GROUPS.map((group) => [group.key, 0]))
  counts.all = candidates.length
  for (const candidate of candidates) counts[resultGroup(candidate)] += 1
  return counts
}

// The candidates in the chosen group whose name contains the search text.
export function filterCandidates(candidates, group, query) {
  const text = query.trim().toLowerCase()
  return candidates.filter(
    (candidate) =>
      (group === 'all' || resultGroup(candidate) === group) &&
      (!text || candidate.full_name.toLowerCase().includes(text)),
  )
}
