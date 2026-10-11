// A job description draft is text that contains a line starting with "# ",
// the job title. This mirrors the rule the backend uses, so a reply that is
// still being written can already be shown as a description card.
export function splitDraft(text) {
  const lines = text.split('\n')
  const index = lines.findIndex((line) => line.startsWith('# ') && line.slice(2).trim())
  if (index === -1) return null
  return {
    intro: lines.slice(0, index).join('\n').trim(),
    title: lines[index].slice(2).trim(),
    body: lines.slice(index + 1).join('\n').trim(),
  }
}
