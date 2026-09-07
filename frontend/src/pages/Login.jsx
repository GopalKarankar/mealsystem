import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import api from '../utils/api'
import { setToken } from '../utils/auth'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      const response = await api.post('/auth/login', { email, password })
      setToken(response.data.access_token)
      navigate('/')
    } catch (err) {
      const message = err.response?.data?.detail || 'Invalid email or password'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleGoogleLogin = async (credentialResponse) => {
    setError('')
    try {
      const response = await api.post('/auth/google', { id_token: credentialResponse.credential })
      setToken(response.data.access_token)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Google sign-in failed')
    }
  }

  const handleGoogleError = () => {
    setError('Google sign-in failed')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-primary-white">
      <div className="max-w-md w-full px-6">
        <h1 className="text-2xl font-bold mb-6 text-primary-black">Login</h1>

        {error && (
          <div
            className="mb-4 p-4 bg-red-50 border border-status-error rounded-md text-status-error"
            role="alert"
            aria-live="polite"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-primary-black mb-2">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 min-h-11 border border-primary-border rounded-md bg-primary-white text-primary-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-black focus:ring-offset-2 transition-all"
              placeholder="you@example.com"
              disabled={isLoading}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-primary-black mb-2">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 min-h-11 border border-primary-border rounded-md bg-primary-white text-primary-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-black focus:ring-offset-2 transition-all"
              placeholder="••••••••"
              disabled={isLoading}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full px-4 py-3 min-h-11 bg-primary-black text-primary-white font-medium rounded-md hover:bg-opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {isLoading ? 'Logging in…' : 'Login'}
          </button>
        </form>

        <div className="my-6 flex items-center gap-4">
          <div className="flex-1 border-t border-primary-border"></div>
          <span className="text-sm text-gray-500">or</span>
          <div className="flex-1 border-t border-primary-border"></div>
        </div>

        <div className="flex justify-center">
          <GoogleLogin
            onSuccess={handleGoogleLogin}
            onError={handleGoogleError}
            theme="outline"
            size="large"
          />
        </div>

        <p className="mt-6 text-center text-sm text-gray-600">
          Don't have an account?{' '}
          <Link to="/register" className="text-primary-black font-medium hover:underline">
            Register here
          </Link>
        </p>
      </div>
    </div>
  )
}
