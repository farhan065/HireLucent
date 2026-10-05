import { BookOpen, LayoutDashboard } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'
import Logo from '../components/Logo.jsx'

const NAV_ITEMS = [{ to: '/app', label: 'Dashboard', icon: LayoutDashboard, end: true }]

// Screens that are built in later tasks. Shown so the layout is complete.
const UPCOMING_ITEMS = [{ label: 'Knowledge Base', icon: BookOpen }]

function navClass({ isActive }) {
  const base = 'flex min-h-11 items-center gap-3 rounded-xl px-3.5 text-[15px] font-semibold'
  return isActive ? `${base} bg-tint text-brand-dark` : `${base} text-body hover:bg-mist`
}

// The interviewer workspace: navigation on the left, the current page on the right.
export default function AppLayout() {
  return (
    <div className="min-h-screen bg-mist md:flex">
      <aside className="flex flex-col gap-6 border-b border-line bg-white p-4 md:w-64 md:border-b-0 md:border-r md:px-4 md:py-6">
        <div className="px-2">
          <Logo to="/app" />
        </div>
        <nav aria-label="Workspace" className="flex gap-1.5 md:flex-col">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={navClass}>
              <Icon className="size-5" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
          {UPCOMING_ITEMS.map(({ label, icon: Icon }) => (
            <span
              key={label}
              className="flex min-h-11 items-center gap-3 rounded-xl px-3.5 text-[15px] font-semibold text-body/60"
            >
              <Icon className="size-5" aria-hidden="true" />
              {label}
              <span className="ml-auto hidden text-xs font-medium md:inline">Soon</span>
            </span>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-6 md:p-10">
        <Outlet />
      </main>
    </div>
  )
}