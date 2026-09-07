export function getToken() {
  return localStorage.getItem('access_token')
}

export function setToken(token) {
  localStorage.setItem('access_token', token)
}

export function removeToken() {
  localStorage.removeItem('access_token')
}

export function isTokenValid() {
  const token = getToken()
  if (!token) return false

  try {
    const parts = token.split('.')
    if (parts.length !== 3) return false

    const payload = JSON.parse(atob(parts[1]))
    if (!payload.exp) return false

    return payload.exp * 1000 > Date.now()
  } catch (error) {
    return false
  }
}

export function logout() {
  removeToken()
  window.location.href = '/login'
}
