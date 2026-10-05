// Temporary page that confirms the design tokens and fonts are working.
// It is replaced by the real pages in the next step.
export default function App() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-mist p-6">
      <section className="w-full max-w-md rounded-card border border-line bg-white p-8 shadow-card">
        <p className="text-sm font-semibold uppercase tracking-widest text-brand">
          Design tokens
        </p>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight">
          Hire<span className="text-brand">Lucent</span>
        </h1>
        <p className="mt-3 leading-relaxed">
          Navy heading, slate body text, a white card on a pale-blue page.
        </p>
        <button
          type="button"
          className="mt-6 min-h-11 rounded-full bg-brand px-6 font-display font-bold text-white shadow-button hover:bg-brand-dark"
        >
          Farhan button
        </button>
      </section>
    </main>
  )
}