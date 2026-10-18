import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'
import RequireInterviewer from './auth/RequireInterviewer.jsx'
import AppLayout from './layouts/AppLayout.jsx'
import AssessmentPage from './pages/AssessmentPage.jsx'
import ComparePage from './pages/ComparePage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import ApplicationsTab from './pages/job/ApplicationsTab.jsx'
import AssessmentsTab from './pages/job/AssessmentsTab.jsx'
import InterviewsTab from './pages/job/InterviewsTab.jsx'
import ScreeningTab from './pages/job/ScreeningTab.jsx'
import JobPage, { JobIndex } from './pages/JobPage.jsx'
import JobsPage from './pages/JobsPage.jsx'
import KnowledgeBasePage from './pages/KnowledgeBasePage.jsx'
import LandingPage from './pages/LandingPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import TranscriptPage from './pages/TranscriptPage.jsx'

// The AI Agent and the video pages are loaded only when opened, so their
// libraries do not slow down the rest of the app.
const AssistantPage = lazy(() => import('./pages/AssistantPage.jsx'))
const InterviewRoomPage = lazy(() => import('./pages/InterviewRoomPage.jsx'))
// The candidate's private interview link. Candidates never sign in.
const InterviewJoinPage = lazy(() => import('./pages/InterviewJoinPage.jsx'))

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/interview/:token"
        element={
          <Suspense fallback={null}>
            <InterviewJoinPage />
          </Suspense>
        }
      />
      {/* Everything under /app is for signed-in interviewers only. */}
      <Route element={<RequireInterviewer />}>
        {/* The interview room fills the screen, without the sidebar. */}
        <Route
          path="/app/interviews/:sessionId/room"
          element={
            <Suspense fallback={null}>
              <InterviewRoomPage />
            </Suspense>
          }
        />
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="jobs/:jobId" element={<JobPage />}>
            <Route index element={<JobIndex />} />
            <Route path="applications" element={<ApplicationsTab />} />
            <Route path="screening" element={<ScreeningTab />} />
            <Route path="interviews" element={<InterviewsTab />} />
            <Route path="assessments" element={<AssessmentsTab />} />
          </Route>
          <Route path="jobs/:jobId/compare" element={<ComparePage />} />
          <Route path="interviews/:sessionId/transcript" element={<TranscriptPage />} />
          <Route path="interviews/:sessionId/assessment" element={<AssessmentPage />} />
          <Route
            path="assistant/:threadId?"
            element={
              <Suspense fallback={null}>
                <AssistantPage />
              </Suspense>
            }
          />
          <Route path="knowledge" element={<KnowledgeBasePage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
