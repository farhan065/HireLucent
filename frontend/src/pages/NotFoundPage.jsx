import Button from '../components/Button.jsx'
import Logo from '../components/Logo.jsx'

export default function NotFoundPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-mist p-6 text-center">
      <Logo />
      <h1 className="text-3xl font-extrabold tracking-tight">Page not found</h1>
      <p>The page you are looking for does not exist or has moved.</p>
      <Button to="/">Back to home</Button>
    </main>
  )
}