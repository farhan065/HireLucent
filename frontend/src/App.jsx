import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'
import RequireInterviewer from './auth/RequireInterviewer.jsx'
import AppLayout from './layouts/AppLayout.jsx'
import AssistantPage from './pages/AssistantPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import ApplicationsTab from './pages/job/ApplicationsTab.jsx'
import ScreeningTab from './pages/job/ScreeningTab.jsx'
import JobPage, { JobIndex } from './pages/JobPage.jsx'
import JobsPage from './pages/JobsPage.jsx'
import KnowledgeBasePage from './pages/KnowledgeBasePage.jsx'
import LandingPage from './pages/LandingPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'

// Video pages are loaded only when opened, so the video library does not
// slow down the rest of the app.
const LiveKitTestPage = lazy(() => import('./pages/LiveKitTestPage.jsx'))

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      {/* Everything under /app is for signed-in interviewers only. */}
      <Route element={<RequireInterviewer />}>
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="jobs/:jobId" element={<JobPage />}>
            <Route index element={<JobIndex />} />
            <Route path="applications" element={<ApplicationsTab />} />
            <Route path="screening" element={<ScreeningTab />} />
          </Route>
          <Route path="assistant/:threadId?" element={<AssistantPage />} />
          <Route path="knowledge" element={<KnowledgeBasePage />} />
          {/* Temporary video check, removed when the interview room is built. */}
          <Route
            path="livekit-test"
            element={
              <Suspense fallback={null}>
                <LiveKitTestPage />
              </Suspense>
            }
          />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
