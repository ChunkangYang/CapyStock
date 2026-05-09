const BASE = import.meta.env.VITE_API_BASE || '/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`${status}: ${detail}`);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE}${path}`;
  // 有 body 且尚未設 Content-Type 時自動補 application/json
  if (init?.body && typeof init.body === 'string') {
    init = {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    };
  }
  const response = await fetch(url, init);

  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}
