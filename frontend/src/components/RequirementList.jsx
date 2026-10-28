const GROUPS = [
  {
    priority: 'must_have',
    label: 'Must-have',
    heading: 'text-brand-dark',
    dot: 'bg-brand',
    text: 'text-navy',
  },
  {
    priority: 'preferred',
    label: 'Preferred',
    heading: 'text-body',
    dot: 'bg-brand/35',
    text: 'text-navy/75',
  },
]

// Requirements as two short lists, must-haves first. The two groups share
// one shape and differ slightly in colour, so long text stays easy to read.
export default function RequirementList({ items }) {
  return (
    <div className="flex flex-col gap-3">
      {GROUPS.map((group) => {
        const matching = items.filter((item) => item.priority === group.priority)
        return (
          <div key={group.priority} className="flex flex-col gap-1.5">
            <h4 className={`text-[13px] font-semibold ${group.heading}`}>{group.label}</h4>
            {matching.length === 0 ? (
              <p className="text-sm">None</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {matching.map((item) => (
                  <li key={item.id} className={`flex gap-2.5 text-sm ${group.text}`}>
                    <span
                      aria-hidden="true"
                      className={`mt-1.5 size-2 shrink-0 rounded-full ${group.dot}`}
                    />
                    {item.text}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </div>
  )
}
