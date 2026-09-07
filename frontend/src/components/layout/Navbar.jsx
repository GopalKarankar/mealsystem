import Container from './Container'

export default function Navbar() {
  return (
    <nav className="sticky top-0 z-10 bg-primary-white border-b border-primary-border shadow-sm animate-slide-up">
      <Container className="py-4 flex items-center justify-center sm:justify-start">
        <span className="text-2xl" role="img" aria-label="Fork and plate">🍽️</span>
        <span className="ml-2 text-xl font-bold tracking-tight text-primary-black">
          Meal Tracker
        </span>
      </Container>
    </nav>
  )
}
