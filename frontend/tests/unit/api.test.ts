import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api, ApiError } from '$lib/api';

describe('api', () => {
  let fetchMock: any;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  it('should return parsed JSON on success', async () => {
    const mockData = { status: 'ok', version: '1.0' };
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });

    const result = await api('/health');
    expect(result).toEqual(mockData);
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/health', undefined);
  });

  it('should throw ApiError on 4xx status', async () => {
    const errorDetail = 'Not found';
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      text: async () => errorDetail,
    });

    try {
      await api('/nonexistent');
      throw new Error('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      if (error instanceof ApiError) {
        expect(error.status).toBe(404);
        expect(error.detail).toBe(errorDetail);
      }
    }
  });

  it('should throw ApiError on 5xx status', async () => {
    const errorDetail = 'Internal server error';
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: async () => errorDetail,
    });

    try {
      await api('/error');
      throw new Error('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      if (error instanceof ApiError) {
        expect(error.status).toBe(500);
        expect(error.detail).toBe(errorDetail);
      }
    }
  });

  it('should pass through RequestInit', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    await api('/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ foo: 'bar' }),
    });

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ foo: 'bar' }),
    });
  });

});
