import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import api from '../utils/api'
import { setToken } from '../utils/auth'

export default function Login() {
  const [error, setError] = useState('')
  const navigate = useNavigate()

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

        <div className="flex justify-center">
          <GoogleLogin
            onSuccess={handleGoogleLogin}
            onError={handleGoogleError}
            theme="outline"
            size="large"
          />
        </div>
      </div>
    </div>
  )
}
