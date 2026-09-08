// API client with JWT authentication
const API_BASE_URL = '';  // Same origin (empty string means current domain)
const API_TIMEOUT = 30000;  // 30 seconds

async function apiRequest(endpoint, options = {}) {
  const {
    method = 'GET',
    body = null,
    headers = {},
  } = options;

  const token = getToken();
  const authHeaders = {
    'Content-Type': 'application/json',
    ...headers,
  };

  if (token) {
    authHeaders['Authorization'] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);

  try {
    const response = await fetch(
      `${API_BASE_URL}${endpoint}`,
      {
        method,
        headers: authHeaders,
        body: body ? JSON.stringify(body) : null,
        signal: controller.signal,
      }
    );

    clearTimeout(timeoutId);

    // Handle 401 - auto logout
    if (response.status === 401) {
      removeToken();
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}

async function apiGet(endpoint) {
  const response = await apiRequest(endpoint, { method: 'GET' });
  return response.json();
}

async function apiPost(endpoint, body) {
  const response = await apiRequest(endpoint, {
    method: 'POST',
    body,
  });
  return response.json();
}

async function apiPatch(endpoint, body) {
  const response = await apiRequest(endpoint, {
    method: 'PATCH',
    body,
  });
  return response.json();
}

async function apiDelete(endpoint) {
  const response = await apiRequest(endpoint, { method: 'DELETE' });
  return response.status === 204 ? null : response.json();
}

// Multipart for file uploads
async function apiPostFile(endpoint, formData) {
  const token = getToken();
  const headers = {};

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);

  try {
    const response = await fetch(
      `${API_BASE_URL}${endpoint}`,
      {
        method: 'POST',
        headers,
        body: formData,
        signal: controller.signal,
      }
    );

    clearTimeout(timeoutId);

    if (response.status === 401) {
      removeToken();
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}
