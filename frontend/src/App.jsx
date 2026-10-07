import { Route, Routes } from 'react-router'
import RequireInterviewer from './auth/RequireInterviewer.jsx'
import AppLayout from './layouts/AppLayout.jsx'
import AssistantPage from './pages/AssistantPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import KnowledgeBasePage from './pages/KnowledgeBasePage.jsx'
import LandingPage from './pages/LandingPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      {/* Everything under /app is for signed-in interviewers only. */}
      <Route element={<RequireInterviewer />}>
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="assistant/:threadId?" element={<AssistantPage />} />
          <Route path="knowledge" element={<KnowledgeBasePage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
