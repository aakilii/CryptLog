import { apiClient, LoginRequest, RegisterRequest, UserInfo } from './api-client'

export interface AuthState {
  isAuthenticated: boolean
  user: UserInfo | null
  token: string | null
}

class AuthService {
  private listeners: Set<(state: AuthState) => void> = new Set()
  private state: AuthState = {
    isAuthenticated: false,
    user: null,
    token: null,
  }

  constructor() {
    if (typeof window !== 'undefined') {
      this.loadFromStorage()
    }
  }

  private loadFromStorage() {
    const token = localStorage.getItem('auth_token')
    if (token) {
      this.state.token = token
      this.state.isAuthenticated = true
      // Try to load user info
      this.getCurrentUser().catch(() => {
        // Token might be invalid, clear it
        this.logout()
      })
    }
  }

  subscribe(listener: (state: AuthState) => void) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  private notify() {
    this.listeners.forEach((listener) => listener(this.state))
  }

  getState(): AuthState {
    return { ...this.state }
  }

  async register(credentials: RegisterRequest): Promise<UserInfo> {
    try {
      const response = await apiClient.register(credentials)
      return response.user
    } catch (error) {
      throw new Error(
        error instanceof Error ? error.message : 'Registration failed'
      )
    }
  }

  async login(credentials: LoginRequest): Promise<UserInfo> {
    try {
      const response = await apiClient.login(credentials)
      this.state = {
        isAuthenticated: true,
        user: response.user,
        token: response.access_token,
      }
      this.notify()
      return response.user
    } catch (error) {
      throw new Error(
        error instanceof Error ? error.message : 'Login failed'
      )
    }
  }

  async getCurrentUser(): Promise<UserInfo> {
    try {
      const user = await apiClient.getCurrentUser()
      this.state.user = user
      this.state.isAuthenticated = true
      this.notify()
      return user
    } catch (error) {
      this.logout()
      throw error
    }
  }

  async logout(): Promise<void> {
    try {
      await apiClient.logout()
    } catch (error) {
      // Continue with logout even if API call fails
      console.error('Logout API error:', error)
    } finally {
      this.state = {
        isAuthenticated: false,
        user: null,
        token: null,
      }
      this.notify()
    }
  }

  isAuthenticated(): boolean {
    return this.state.isAuthenticated && this.state.token !== null
  }

  getUser(): UserInfo | null {
    return this.state.user
  }
}

export const authService = new AuthService()

