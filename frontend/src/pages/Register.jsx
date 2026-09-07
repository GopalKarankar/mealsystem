import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { setToken } from '../utils/auth'

export default function Register() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setIsLoading(true)

    try {
      const response = await api.post('/auth/register', { username, email, password })
      setToken(response.data.access_token)
      navigate('/')
    } catch (err) {
      let message = 'Registration failed. Please try again.'
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail
        if (typeof detail === 'string') {
          message = detail
        } else if (Array.isArray(detail)) {
          message = detail.map((e) => e.msg).join(', ')
        }
      }
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-primary-white">
      <div className="max-w-md w-full px-6">
        <h1 className="text-2xl font-bold mb-6 text-primary-black">Create Account</h1>

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
            <label htmlFor="username" className="block text-sm font-medium text-primary-black mb-2">
              Username
            </label>
            <input
              id="username"
              type="text"
              required
              minLength={3}
              maxLength={50}
              pattern="[a-zA-Z0-9_]+"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 min-h-11 border border-primary-border rounded-md bg-primary-white text-primary-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-black focus:ring-offset-2 transition-all"
              placeholder="john_doe"
              disabled={isLoading}
            />
            <p className="text-xs text-gray-500 mt-1">3-50 characters, letters/numbers/underscore only</p>
          </div>

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
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 min-h-11 border border-primary-border rounded-md bg-primary-white text-primary-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-black focus:ring-offset-2 transition-all"
              placeholder="••••••••"
              disabled={isLoading}
            />
            <p className="text-xs text-gray-500 mt-1">At least 8 characters</p>
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-primary-black mb-2">
              Confirm Password
            </label>
            <input
              id="confirmPassword"
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
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
            {isLoading ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-600">
          Already have an account?{' '}
          <Link to="/login" className="text-primary-black font-medium hover:underline">
            Login here
          </Link>
        </p>
      </div>
    </div>
  )
}
