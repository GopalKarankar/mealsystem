export default function Spinner({ size = 'md' }) {
  const sizeClass = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  }[size]

  return <div className={`${sizeClass} border-2 border-primary-border border-t-primary-black animate-spin`} />
}
