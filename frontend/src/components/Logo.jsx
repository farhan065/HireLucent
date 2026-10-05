import { Link } from 'react-router'

export default function Logo({ to = '/' }) {
  return (
    <Link to={to} className="flex items-center gap-3" aria-label="HireLucent home">
      <img src="/favicon.svg" alt="" className="size-9" />
      <span className="font-display text-[22px] font-extrabold tracking-tight text-navy">
        Hire<span className="text-brand">Lucent</span>
      </span>
    </Link>
  )
}