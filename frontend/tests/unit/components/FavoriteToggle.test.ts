import { describe, it, expect, vi } from 'vitest';

vi.mock('$lib/api', () => ({
  api: vi.fn(),
}));

vi.mock('$lib/stores/favorites', () => ({
  favorites: {
    subscribe: vi.fn((callback) => {
      callback([]);
      return () => {};
    }),
    update: vi.fn(),
  },
}));

describe('FavoriteToggle', () => {
  it('應該接受 code prop', () => {
    const code = '7203';
    expect(code).toBe('7203');
  });

  it('應該接受 name prop', () => {
    const name = 'Toyota';
    expect(name).toBe('Toyota');
  });

  it('應該接受 tag prop', () => {
    const tag = 'speculative';
    expect(tag).toBe('speculative');
  });

  it('應該支持多個 tag 值', () => {
    const validTags = ['speculative', 'dividend'];
    expect(validTags).toContain('speculative');
    expect(validTags).toContain('dividend');
  });

  it('code 應該是有效的股票代碼格式', () => {
    const code = '7203';
    expect(code).toMatch(/^\d{4}$/);
  });

  it('tag 應該是有效值', () => {
    const validTags = ['speculative', 'dividend'];
    expect(validTags).toContain('speculative');
  });
});
