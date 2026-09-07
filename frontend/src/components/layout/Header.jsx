import { logout } from '../../utils/auth'
import Button from '../common/Button'
import Container from './Container'

export default function Header({ onLogout }) {
  const handleLogout = () => {
    onLogout ? onLogout() : logout()
  }

  return (
    <header className="sticky top-0 bg-primary-white border-b border-primary-border shadow-sm">
      <Container className="py-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-primary-black">Meal Dashboard</h1>
        <Button variant="secondary" onClick={handleLogout}>
          Logout
        </Button>
      </Container>
    </header>
  )
}
