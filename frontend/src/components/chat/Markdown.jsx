import ReactMarkdown from 'react-markdown'

// Styles for each kind of Markdown element the assistant writes.
const COMPONENTS = {
  h1: (props) => <h3 className="text-lg font-bold" {...props} />,
  h2: (props) => <h4 className="mt-3 font-display text-[15px] font-bold text-navy" {...props} />,
  h3: (props) => <h5 className="mt-2 font-semibold text-navy" {...props} />,
  p: (props) => <p className="mt-1.5 leading-relaxed" {...props} />,
  ul: (props) => <ul className="mt-1.5 list-disc space-y-1 pl-5" {...props} />,
  ol: (props) => <ol className="mt-1.5 list-decimal space-y-1 pl-5" {...props} />,
  strong: (props) => <strong className="font-semibold text-navy" {...props} />,
}

export default function Markdown({ children }) {
  return <ReactMarkdown components={COMPONENTS}>{children}</ReactMarkdown>
}
