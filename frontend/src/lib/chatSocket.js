import { getAccessToken } from './api.js'

const RECONNECT_DELAY_MS = 2000

// Opens the live connection to the AI Agent and keeps it open.
// onEvent receives each server event; onStatus receives "connecting",
// "connected" or "disconnected".
export function openChatSocket({ onEvent, onStatus }) {
  let socket = null
  let closedByUs = false
  let retryTimer = null

  function connect() {
    onStatus('connecting')
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    socket = new WebSocket(`${protocol}://${window.location.host}/api/chat`)

    // The access token is sent as the first message, never in the address.
    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'auth', token: getAccessToken() }))
    }
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data)
      if (event.type === 'ready') onStatus('connected')
      else onEvent(event)
    }
    socket.onclose = () => {
      onStatus('disconnected')
      if (!closedByUs) retryTimer = setTimeout(connect, RECONNECT_DELAY_MS)
    }
  }

  connect()

  return {
    send(payload) {
      if (socket?.readyState !== WebSocket.OPEN) return false
      socket.send(JSON.stringify(payload))
      return true
    },
    close() {
      closedByUs = true
      clearTimeout(retryTimer)
      socket?.close()
    },
  }
}
