export default function Badge({ variant, label }) {
  const colorClass = {
    green: 'bg-status-success text-primary-white',
    orange: 'bg-status-warning text-primary-white',
    red: 'bg-status-error text-primary-white',
  }[variant]

  const defaultLabel = {
    green: 'High',
    orange: 'Medium',
    red: 'Low',
  }[variant]

  return (
    <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${colorClass}`}>
      {label || defaultLabel}
    </span>
  )
}
