import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import api from '../utils/api'
import { setToken } from '../utils/auth'
import Navbar from '../components/layout/Navbar'

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
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-emerald-50 via-white to-lime-50">
      <Navbar />

      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">

          {/* Login Card */}
          <div className="relative overflow-hidden rounded-3xl border border-white/80 bg-white/90 p-8 shadow-xl shadow-emerald-100/50 backdrop-blur-sm sm:p-10">

            {/* Decorative background shapes */}
            <div className="absolute -right-16 -top-16 h-40 w-40 rounded-full bg-emerald-100/60 blur-2xl" />
            <div className="absolute -bottom-20 -left-16 h-40 w-40 rounded-full bg-lime-100/60 blur-2xl" />

            <div className="relative">

              {/* Icon */}
              <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-100 text-3xl shadow-sm">
                🍽️
              </div>

              {/* Heading */}
              <div className="text-center">
                <h1 className="text-3xl font-bold tracking-tight text-gray-900">
                  Welcome back
                </h1>

                <p className="mt-2 text-sm leading-6 text-gray-500">
                  Sign in to continue tracking your meals
                  <br />
                  and building healthier habits.
                </p>
              </div>

              {/* Error */}
              {error && (
                <div
                  className="mt-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
                  role="alert"
                  aria-live="polite"
                >
                  <span className="mt-0.5 text-base">⚠️</span>

                  <p>{error}</p>
                </div>
              )}

              {/* Divider */}
              <div className="my-8 flex items-center gap-4">
                <div className="h-px flex-1 bg-gray-200" />

                <span className="text-xs font-medium uppercase tracking-wider text-gray-400">
                  Continue with
                </span>

                <div className="h-px flex-1 bg-gray-200" />
              </div>

              {/* Google Login */}
              <div className="flex justify-center">
                <GoogleLogin
                  onSuccess={handleGoogleLogin}
                  onError={handleGoogleError}
                  theme="outline"
                  size="large"
                />
              </div>

              {/* Footer message */}
              <p className="mt-8 text-center text-xs leading-5 text-gray-400">
                By continuing, you agree to use the Meal Tracker
                responsibly and keep your account secure.
              </p>
            </div>
          </div>

          {/* Bottom branding */}
          <p className="mt-6 text-center text-sm text-gray-400">
            Simple tracking. Better habits. 🌱
          </p>
        </div>
      </main>
    </div>
  )
}

