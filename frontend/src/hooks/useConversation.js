import { useCallback, useEffect, useRef, useState } from 'react'
import { apiRequest } from '../lib/api.js'
import { openChatSocket } from '../lib/chatSocket.js'

const CONNECTION_LOST = 'Connection lost. Reconnecting…'

// Everything the AI Agent screen needs for one conversation:
// the current view from the server, the reply being written, and the
// actions the interviewer can take.
export function useConversation(threadId, onStarted, firstMessage) {
  const [view, setView] = useState(null)
  const [streamingText, setStreamingText] = useState('')
  const [pendingText, setPendingText] = useState('')
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('connecting')
  const socketRef = useRef(null)
  const threadIdRef = useRef(threadId)
  const onStartedRef = useRef(onStarted)
  // A message to send as soon as the connection is ready, used when a job is
  // started from the dashboard.
  const firstMessageRef = useRef(firstMessage)

  useEffect(() => {
    threadIdRef.current = threadId
    onStartedRef.current = onStarted
  })

  // One live connection for as long as the screen is open.
  useEffect(() => {
    function handleEvent(event) {
      if (event.type === 'token') {
        setStreamingText((text) => text + event.text)
      } else if (event.type === 'view') {
        const isNew = !threadIdRef.current
        setView(event)
        finishTurn()
        if (isNew) onStartedRef.current?.(event.thread_id)
      } else if (event.type === 'error') {
        setError(event.message)
        finishTurn()
      }
    }

    function finishTurn() {
      setStreamingText('')
      setPendingText('')
      setIsBusy(false)
    }

    function handleStatus(newStatus) {
      setStatus(newStatus)
      const text = firstMessageRef.current
      if (newStatus === 'connected' && text) {
        firstMessageRef.current = null
        socketRef.current.send({ type: 'message', thread_id: null, text })
        setPendingText(text)
        setIsBusy(true)
      }
    }

    socketRef.current = openChatSocket({ onEvent: handleEvent, onStatus: handleStatus })
    return () => socketRef.current.close()
  }, [])

  // Opening an existing conversation loads its full history. The screen is
  // created afresh for each conversation, so this runs once.
  const [initialThreadId] = useState(threadId)
  useEffect(() => {
    if (!initialThreadId) return
    let isCurrent = true
    apiRequest(`/chat/${initialThreadId}`)
      .then((loaded) => isCurrent && setView(loaded))
      .catch((loadError) => isCurrent && setError(loadError.message))
    return () => {
      isCurrent = false
    }
  }, [initialThreadId])

  // Load the view again after a change made outside the conversation, such
  // as editing the requirements from the job brief.
  const reloadView = useCallback(() => {
    if (!threadIdRef.current) return
    apiRequest(`/chat/${threadIdRef.current}`)
      .then(setView)
      .catch((loadError) => setError(loadError.message))
  }, [])

  const send = useCallback((payload, shownText = '') => {
    setError('')
    const sent = socketRef.current.send({ thread_id: threadIdRef.current, ...payload })
    if (!sent) {
      setError(CONNECTION_LOST)
      return
    }
    setPendingText(shownText)
    setIsBusy(true)
  }, [])

  const sendMessage = useCallback(
    (text) => send({ type: 'message', text }, text),
    [send],
  )

  const submitApproval = useCallback(
    (approved, extra = {}) => send({ type: 'approval', approved, ...extra }),
    [send],
  )

  const editDescription = useCallback(
    (title, text) => send({ type: 'edit_description', title, text }),
    [send],
  )

  return {
    view,
    streamingText,
    pendingText,
    isBusy,
    error,
    status,
    sendMessage,
    submitApproval,
    editDescription,
    reloadView,
  }
}
