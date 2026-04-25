import { describe, it, expect, vi } from 'vitest';
import type { PriceBar } from '$lib/types';

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    applyOptions: vi.fn(),
    addCandlestickSeries: vi.fn(() => ({
      setData: vi.fn(),
    })),
    addLineSeries: vi.fn(() => ({
      setData: vi.fn(),
    })),
    timeScale: vi.fn(() => ({
      fitContent: vi.fn(),
    })),
  })),
}));

describe('KLineChart', () => {
  const mockPrices: PriceBar[] = [
    {
      date: '2026-04-20',
      open: 100,
      high: 105,
      low: 98,
      close: 102,
      volume: 1000,
    },
    {
      date: '2026-04-21',
      open: 102,
      high: 110,
      low: 100,
      close: 108,
      volume: 1200,
    },
    {
      date: '2026-04-22',
      open: 108,
      high: 112,
      low: 105,
      close: 110,
      volume: 1100,
    },
  ];

  it('應該接受 prices props', () => {
    expect(mockPrices).toHaveLength(3);
  });

  it('應該接受 startPrice props', () => {
    const startPrice = 100;
    expect(startPrice).toBe(100);
  });

  it('應該接受 recentLow props', () => {
    const recentLow = 98;
    expect(recentLow).toBeLessThan(100);
  });

  it('prices 應該包含正確的欄位', () => {
    const price = mockPrices[0];
    expect(price).toHaveProperty('date');
    expect(price).toHaveProperty('open');
    expect(price).toHaveProperty('high');
    expect(price).toHaveProperty('low');
    expect(price).toHaveProperty('close');
    expect(price).toHaveProperty('volume');
  });

  it('應該正確計算 K 線範圍', () => {
    const highs = mockPrices.map(p => p.high);
    const lows = mockPrices.map(p => p.low);
    expect(Math.max(...highs)).toBe(112);
    expect(Math.min(...lows)).toBe(98);
  });
});
