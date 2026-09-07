import { useState, useEffect, useRef } from 'react'
import api from '../../utils/api'
import { formatDuration } from '../../utils/formatting'
import Button from '../common/Button'
import Spinner from '../common/Spinner'

export default function AudioRecorder({ onMealAdded }) {
  const [status, setStatus] = useState('idle')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [error, setError] = useState('')

  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const timerRef = useRef(null)
  const streamRef = useRef(null)
  const skipUploadRef = useRef(false)

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const startRecording = async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      let mimeType = 'audio/webm'
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus'
      }
      const mediaRecorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        chunksRef.current.push(e.data)
      }

      mediaRecorder.onstop = async () => {
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop())
          streamRef.current = null
        }
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }

        if (!skipUploadRef.current) {
          setStatus('processing')
          await processRecording()
        }
        skipUploadRef.current = false
      }

      mediaRecorder.start()
      setStatus('recording')
      setElapsedSeconds(0)

      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1)
      }, 1000)
    } catch (err) {
      if (err.name === 'NotAllowedError') {
        setError('Microphone permission denied. Please allow access and try again.')
      } else {
        setError('Failed to start recording. Please try again.')
      }
      setStatus('idle')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && status === 'recording') {
      if (elapsedSeconds < 1.5) {
        skipUploadRef.current = true
        mediaRecorderRef.current.stop()
        setError('Recording too short — press Record, speak, then press Stop (at least 1.5 seconds).')
        return
      }
      mediaRecorderRef.current.stop()
    }
  }

  const processRecording = async () => {
    try {
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      const formData = new FormData()
      formData.append('file', blob, 'recording.webm')

      const { data } = await api.post('/meals/voice', formData)
      onMealAdded(data)
      setStatus('idle')
      setElapsedSeconds(0)
    } catch (err) {
      const detail = err.response?.data?.detail
      let message = 'Failed to process audio'
      if (typeof detail === 'string' && detail.trim()) {
        message = detail
      } else if (err.response?.status === 400) {
        message = 'Unsupported audio format'
      } else if (err.response?.status === 413) {
        message = 'Recording is too long'
      } else if (err.response?.status === 422) {
        message = 'Could not understand what you said. Try again with clearer wording.'
      }
      setError(message)
      setStatus('idle')
    }
  }

  return (
    <div className="flex flex-col items-center gap-6 py-8">
      <div className="flex flex-col items-center gap-4">
        {status === 'recording' && (
          <div className="flex items-center gap-3">
            <div className="h-3 w-3 bg-status-error rounded-full animate-pulse" />
            <span className="text-sm font-medium text-primary-black">Recording...</span>
          </div>
        )}

        {status === 'processing' && (
          <div className="flex items-center gap-3">
            <Spinner size="sm" />
            <span className="text-sm font-medium text-primary-black">Processing...</span>
          </div>
        )}

        {status !== 'processing' && (
          <div className="text-sm font-mono text-primary-black h-6">{formatDuration(elapsedSeconds)}</div>
        )}

        <Button
          variant={status === 'recording' ? 'danger' : 'primary'}
          onClick={status === 'recording' ? stopRecording : startRecording}
          isLoading={status === 'processing'}
          className="w-24 h-24 rounded-full text-lg font-bold"
        >
          {status === 'idle' && '🎤 Record'}
          {status === 'recording' && 'Stop'}
          {status === 'processing' && ''}
        </Button>

        {status === 'idle' && (
          <p className="text-xs text-gray-500 text-center max-w-xs">
            e.g. "I had two scrambled eggs, a slice of toast, and a cup of coffee"
          </p>
        )}
      </div>

      {error && (
        <div
          role="alert"
          aria-live="polite"
          className="w-full max-w-md p-4 bg-status-error bg-opacity-10 border border-status-error rounded-md text-status-error text-sm"
        >
          {error}
        </div>
      )}
    </div>
  )
}
