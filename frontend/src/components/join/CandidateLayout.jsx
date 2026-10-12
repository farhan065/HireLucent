// The frame of every candidate page: the HireLucent name and what the page
// is for. The logo is not a link, so candidates stay on their interview.
export default function CandidateLayout({ note, children }) {
  return (
    <div className="flex min-h-screen flex-col bg-mist">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-white px-6 py-5 md:px-10">
        <span className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="size-9" />
          <span className="font-display text-[22px] font-extrabold tracking-tight text-navy">
            Hire<span className="text-brand">Lucent</span>
          </span>
        </span>
        {note && <span className="text-sm">{note}</span>}
      </header>
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-7 px-6 py-10 md:px-10 md:py-11">
        {children}
      </main>
    </div>
  )
}
