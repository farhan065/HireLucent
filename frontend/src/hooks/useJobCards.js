import { useEffect, useState } from 'react'
import { apiRequest } from '../lib/api.js'
import { buildCards, loadWaiting } from '../lib/jobs.js'

// Every job of the interviewer, saved or still being drafted, with the
// number of new applications waiting for each published job.
export function useJobCards() {
  const [cards, setCards] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      const [jobs, conversations] = await Promise.all([
        apiRequest('/jobs'),
        apiRequest('/chat/conversations'),
      ])
      const waiting = await Promise.all(jobs.map(loadWaiting))
      const waitingByJob = new Map(jobs.map((job, index) => [job.id, waiting[index]]))
      return buildCards(jobs, conversations).map((card) => ({
        ...card,
        waiting: card.job ? waitingByJob.get(card.job.id) : 0,
      }))
    }
    load()
      .then(setCards)
      .catch((loadError) => setError(loadError.message))
  }, [])

  return { cards, error }
}
