import Spinner from './Spinner'

export default function Button({
  variant = 'primary',
  isLoading = false,
  disabled = false,
  type = 'button',
  onClick,
  className = '',
  children,
}) {
  const variants = {
    primary: 'bg-primary-black text-primary-white hover:bg-opacity-90',
    secondary: 'bg-primary-gray text-primary-black hover:bg-opacity-80 border border-primary-border',
    danger: 'bg-status-error text-primary-white hover:bg-opacity-90',
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={isLoading || disabled}
      className={`px-4 py-3 min-h-11 rounded-md font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-primary-black focus:ring-offset-2 ${variants[variant]} ${className}`}
    >
      {isLoading && <Spinner size="sm" className="inline mr-2" />}
      {children}
    </button>
  )
}
