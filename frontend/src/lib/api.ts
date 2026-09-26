const API_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ||
  'http://localhost:8100'

export class ApiError extends Error {
  status: number

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

interface FetchOptions {
  method?: string
  body?: unknown
  token?: string
}

export async function apiFetch<T = Record<string, unknown>>(
  path: string,
  { method = 'GET', body, token }: FetchOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  let data: Record<string, unknown> | null = null
  try {
    data = await resp.json()
  } catch {
    /* non-JSON response */
  }

  if (!resp.ok) {
    const detail =
      (data && typeof data.detail === 'string'
        ? data.detail
        : JSON.stringify(data?.detail)) || `Request failed (${resp.status})`
    throw new ApiError(resp.status, detail)
  }
  return data as T
}
