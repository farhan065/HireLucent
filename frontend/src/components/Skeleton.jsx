// A grey placeholder in the shape of content that is still loading.
export default function Skeleton({ className = '' }) {
  return <div aria-hidden="true" className={`animate-shimmer rounded-lg ${className}`} />
}
