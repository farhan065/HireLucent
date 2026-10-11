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

const TOKEN_KEY = 'hirelucent_access_token'

// The token is kept in sessionStorage: it survives a page refresh and is
// removed when the browser tab is closed.
export function getAccessToken() {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setAccessToken(token) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token)
  else sessionStorage.removeItem(TOKEN_KEY)
}

export async function apiRequest(path, { method = 'GET', body } = {}) {
  // A FormData body is a file upload. The browser sets its content type.
  const isUpload = body instanceof FormData
  const headers = {}
  if (body !== undefined && !isUpload) headers['Content-Type'] = 'application/json'

  const token = getAccessToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined || isUpload ? body : JSON.stringify(body),
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

// Downloads a file that needs the access token, such as a candidate's CV.
export async function apiFile(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${getAccessToken()}` },
  }).catch(() => null)
  if (!response?.ok) {
    throw new ApiError(response?.status ?? 0, 'file_error', 'The file could not be opened.')
  }
  return response.blob()
}
