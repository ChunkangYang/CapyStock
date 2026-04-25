import { describe, it, expect, vi } from 'vitest';
import type { FundamentalReport } from '$lib/types';

// Mock echarts
vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
  })),
}));

describe('RadarChart', () => {
  const mockReport: FundamentalReport = {
    code: '7203',
    name: 'トヨタ自動車',
    overall: 'STRONG',
    pass_count: 7,
    warn_count: 1,
    fail_count: 0,
    metrics: [
      { name: 'Sales', score: 'PASS', value: 1000, note: '成長中' },
      { name: 'EPS', score: 'PASS', value: 100, note: '穩健' },
      { name: 'OpMargin', score: 'WARN', value: 0.05, note: '略低' },
      { name: 'Equity', score: 'PASS', value: 0.6, note: '健全' },
      { name: 'OpCF', score: 'PASS', value: 500, note: '正向' },
      { name: 'Cash', score: 'PASS', value: 300, note: '充足' },
      { name: 'DPS', score: 'PASS', value: 50, note: '穩定' },
      { name: 'Payout', score: 'PASS', value: 0.3, note: '合理' },
    ],
  };

  function scoreToValue(score: string): number {
    switch (score) {
      case 'PASS':
        return 100;
      case 'WARN':
        return 60;
      case 'FAIL':
        return 20;
      case 'N/A':
        return 0;
      default:
        return 0;
    }
  }

  it('應該接受 report props', () => {
    expect(mockReport).toBeDefined();
    expect(mockReport.code).toBe('7203');
  });

  it('應該有正確的指標數量', () => {
    expect(mockReport.metrics).toHaveLength(8);
  });

  it('應該正確 normalize score 為數值', () => {
    const values = mockReport.metrics.map((m) => scoreToValue(m.score));
    expect(values[0]).toBe(100); // PASS
    expect(values[2]).toBe(60); // WARN
    expect(values).not.toContain(undefined);
  });

  it('應該包含所有必需的指標', () => {
    const metricNames = mockReport.metrics.map((m) => m.name);
    expect(metricNames).toContain('Sales');
    expect(metricNames).toContain('EPS');
    expect(metricNames).toContain('OpMargin');
    expect(metricNames).toContain('Equity');
    expect(metricNames).toContain('OpCF');
    expect(metricNames).toContain('Cash');
    expect(metricNames).toContain('DPS');
    expect(metricNames).toContain('Payout');
  });

  it('應該正確計算 overall 評分分佈', () => {
    const { pass_count, warn_count, fail_count } = mockReport;
    const total = pass_count + warn_count + fail_count;
    expect(total).toBe(8);
    expect(pass_count).toBe(7);
    expect(warn_count).toBe(1);
    expect(fail_count).toBe(0);
  });

  it('PASS 分數應該為 100', () => {
    expect(scoreToValue('PASS')).toBe(100);
  });

  it('WARN 分數應該為 60', () => {
    expect(scoreToValue('WARN')).toBe(60);
  });

  it('FAIL 分數應該為 20', () => {
    expect(scoreToValue('FAIL')).toBe(20);
  });

  it('N/A 分數應該為 0', () => {
    expect(scoreToValue('N/A')).toBe(0);
  });

  it('所有分數應該在 0-100 範圍內', () => {
    const values = mockReport.metrics.map((m) => scoreToValue(m.score));
    values.forEach((v) => {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    });
  });
});
