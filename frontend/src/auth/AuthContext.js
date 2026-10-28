import { createContext, useContext } from 'react'

export const AuthContext = createContext(null)

// Gives any component the signed-in user and the login and logout actions.
export function useAuth() {
  return useContext(AuthContext)
}