// Requirements as chips: dark for must-haves, light for preferred.
export default function RequirementChips({ items, priority }) {
  const matching = priority ? items.filter((item) => item.priority === priority) : items
  if (matching.length === 0) return <span className="text-sm">None</span>
  return matching.map((item) => (
    <span
      key={item.id}
      className={`rounded-full px-3 py-1 text-[13px] font-semibold ${
        item.priority === 'must_have' ? 'bg-navy text-white' : 'bg-mist text-body'
      }`}
    >
      {item.text}
    </span>
  ))
}
