import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from './AuthContext.js'

// Guards the interviewer workspace. Anyone who is not a signed-in
// interviewer is sent to the login page.
export default function RequireInterviewer() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <p role="status" className="flex min-h-screen items-center justify-center bg-mist">
        Loading your workspace…
      </p>
    )
  }
  if (user?.role !== 'interviewer') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}