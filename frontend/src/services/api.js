const base = (import.meta.env?.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
let token = globalThis.sessionStorage?.getItem('streamdoctor.session') || '';

export function setToken(value) {
  token = value || '';
  if (token) sessionStorage.setItem('streamdoctor.session', token);
  else sessionStorage.removeItem('streamdoctor.session');
}
export const hasSession = () => Boolean(token);

export function errorMessage(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => `${item.loc?.slice(1).join('.') || 'Request'}: ${item.msg}`).join('; ');
  if (detail?.message) return detail.message + (detail.missing_fields?.length ? `: ${detail.missing_fields.join(', ')}` : '');
  return 'The request could not be completed. Please try again.';
}

export async function request(path, { method = 'GET', body, signal, blob = false } = {}) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const multipart = body instanceof FormData;
  if (body && !multipart) headers['Content-Type'] = 'application/json';
  const response = await fetch(base + path, { method, headers, body: body ? (multipart ? body : JSON.stringify(body)) : undefined, signal });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401 && !path.startsWith('/auth/')) {
      setToken('');
      globalThis.dispatchEvent?.(new Event('session-expired'));
    }
    const error = new Error(errorMessage(payload.detail));
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  return blob ? response.blob() : response.json();
}

export async function allSites() {
  const items = [];
  for (let offset = 0; ; offset += 100) {
    const page = await request(`/sites?limit=100&offset=${offset}`);
    items.push(...page.items);
    if (items.length >= page.total || !page.items.length) return items;
  }
}

export const reportPath = id => `/reports/${encodeURIComponent(id)}`;
export const photoPath = (reportId, photoId) => `${reportPath(reportId)}/photos/${encodeURIComponent(photoId)}/content`;
export const label = value => String(value ?? 'Unknown').replaceAll('_', ' ');
export function observationPayload(form) {
  const { observed_at, ph, ...fields } = form;
  return { ...fields, observed_at: new Date(observed_at).toISOString(), ph: ph === '' || ph == null ? null : Number(ph) };
}
