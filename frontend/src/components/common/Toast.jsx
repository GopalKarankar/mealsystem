import { useState, useEffect } from 'react'

export function useToast() {
  const [toast, setToast] = useState(null)

  const showToast = (type, message) => {
    setToast({ type, message })
  }

  const dismissToast = () => {
    setToast(null)
  }

  return { toast, showToast, dismissToast }
}

export default function Toast({ toast, onDismiss }) {
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(onDismiss, 4000)
      return () => clearTimeout(timer)
    }
  }, [toast, onDismiss])

  if (!toast) return null

  const bgColor = {
    success: 'bg-status-success',
    error: 'bg-status-error',
    info: 'bg-status-info',
  }[toast.type]

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-4 right-4 ${bgColor} text-primary-white px-6 py-4 rounded-md shadow-lg animate-slide-up`}
    >
      <div className="flex items-center justify-between gap-4">
        <p>{toast.message}</p>
        <button
          onClick={onDismiss}
          className="text-primary-white hover:opacity-80"
          aria-label="Dismiss notification"
        >
          ✕
        </button>
      </div>
    </div>
  )
}
