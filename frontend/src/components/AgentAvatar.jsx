// The face of the AI Agent, used wherever the agent is named or speaks.
export default function AgentAvatar({ className = 'size-6' }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={`shrink-0 ${className}`}>
      <circle cx="16" cy="16" r="16" fill="#1557e0" />
      <line x1="16" y1="5.6" x2="16" y2="9" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="16" cy="5.2" r="1.7" fill="#a9c8ff" />
      <rect x="5" y="13.4" width="3" height="5.2" rx="1.4" fill="#a9c8ff" />
      <rect x="24" y="13.4" width="3" height="5.2" rx="1.4" fill="#a9c8ff" />
      <rect x="7.5" y="9" width="17" height="14" rx="4.8" fill="#fff" />
      <circle cx="12.6" cy="15" r="1.9" fill="#0b1f4b" />
      <circle cx="19.4" cy="15" r="1.9" fill="#0b1f4b" />
      <path
        d="M12.6 18.9c1 .9 2.1 1.3 3.4 1.3s2.4-.4 3.4-1.3"
        fill="none"
        stroke="#1557e0"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <rect x="11.5" y="24.2" width="9" height="2.6" rx="1.3" fill="#a9c8ff" />
    </svg>
  )
}
