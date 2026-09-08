// JWT token management
const AUTH_KEY = 'access_token';
const USER_ID_KEY = 'user_id';

function getToken() {
  return localStorage.getItem(AUTH_KEY);
}

function setToken(token, userId, expiresIn) {
  localStorage.setItem(AUTH_KEY, token);
  localStorage.setItem(USER_ID_KEY, userId);
  // Store expiry time
  const expiryTime = Date.now() + (expiresIn * 1000);
  localStorage.setItem('token_expiry', expiryTime);
}

function removeToken() {
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(USER_ID_KEY);
  localStorage.removeItem('token_expiry');
}

function isTokenValid() {
  const token = getToken();
  if (!token) return false;

  try {
    // Decode JWT payload (base64 decode the middle part)
    const parts = token.split('.');
    if (parts.length !== 3) return false;

    const payload = JSON.parse(atob(parts[1]));
    const now = Date.now() / 1000;

    return payload.exp > now;
  } catch (e) {
    return false;
  }
}

function logout() {
  removeToken();
  window.location.href = '/login';
}

// Auto-logout if token is expired on page load
if (!isTokenValid() && getToken()) {
  logout();
}
