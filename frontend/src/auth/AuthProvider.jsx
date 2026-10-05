import { useEffect, useState } from 'react'
import { apiRequest, getAccessToken, setAccessToken } from '../lib/api.js'
import { AuthContext } from './AuthContext.js'

// Holds the signed-in interviewer for the whole app.
export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // Only "loading" at the start if there is a saved token to check.
  const [isLoading, setIsLoading] = useState(() => Boolean(getAccessToken()))

  // After a page refresh, use the saved token to load the user again.
  useEffect(() => {
    if (!getAccessToken()) return
    apiRequest('/auth/me')
      .then(setUser)
      .catch(() => setAccessToken(null))
      .finally(() => setIsLoading(false))
  }, [])

  async function login(email, password) {
    const { access_token } = await apiRequest('/auth/login', {
      method: 'POST',
      body: { email, password },
    })
    setAccessToken(access_token)
    try {
      setUser(await apiRequest('/auth/me'))
    } catch (error) {
      setAccessToken(null)
      throw error
    }
  }

  function logout() {
    setAccessToken(null)
    setUser(null)
  }

  return <AuthContext value={{ user, isLoading, login, logout }}>{children}</AuthContext>
}