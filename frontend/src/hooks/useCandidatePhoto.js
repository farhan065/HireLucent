import { useEffect, useState } from 'react'
import { apiFile } from '../lib/api.js'

// The candidate's application photo (F7) as an address the page can show,
// loaded with the interviewer's sign-in. null while loading or without a
// photo. The copy in memory is released when the room closes.
export function useCandidatePhoto(candidateId, hasPhoto) {
  const [url, setUrl] = useState(null)

  useEffect(() => {
    if (!candidateId || !hasPhoto) return undefined
    let address = null
    let isCurrent = true
    apiFile(`/candidates/${candidateId}/photo`)
      .then((blob) => {
        if (!isCurrent) return
        address = URL.createObjectURL(blob)
        setUrl(address)
      })
      .catch(() => {})
    return () => {
      isCurrent = false
      if (address) URL.revokeObjectURL(address)
      setUrl(null)
    }
  }, [candidateId, hasPhoto])

  return hasPhoto ? url : null
}
