export default function Container({ className = '', children }) {
  return <div className={`max-w-4xl mx-auto px-4 sm:px-6 ${className}`}>{children}</div>
}
