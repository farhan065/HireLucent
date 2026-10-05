// Small client for the HireLucent backend. All requests go to /api,
// which the dev server (and nginx in Docker) forwards to FastAPI.

const API_BASE = '/api'

export class ApiError extends Error {
  constructor(status, code, message, details = []) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

let accessToken = null

// The token is kept in memory only, never in localStorage.
export function setAccessToken(token) {
  accessToken = token
}

export async function apiRequest(path, { method = 'GET', body } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`

  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the server. Check that it is running.')
  }

  if (response.status === 204) return null

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    // The backend returns every error as { error: { code, message, details } }.
    const error = data?.error
    throw new ApiError(
      response.status,
      error?.code ?? 'unknown_error',
      error?.message ?? 'Something went wrong. Please try again.',
      error?.details ?? [],
    )
  }
  return data
}