export default function Card({ className = '', children }) {
  return <div className={`bg-primary-white rounded-lg shadow-md p-6 ${className}`}>{children}</div>
}
