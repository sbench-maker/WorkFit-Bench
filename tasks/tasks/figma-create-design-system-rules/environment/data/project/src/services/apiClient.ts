type RequestOptions = Omit<RequestInit, 'credentials'>;
export const apiClient = {
  async get<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await fetch(`/api${path}`, { ...options, credentials: 'include' });
    if (!response.ok) throw new Error(`Request failed: ${response.status}`);
    return response.json() as Promise<T>;
  },
};
