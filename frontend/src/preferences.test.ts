import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { greetingText, normalizeName, periodAt, readPreference, sessionGreeting, writePreference } from './preferences';
import { dateLabel, metadataLabel, timestampOrder } from './format';

beforeEach(() => { localStorage.clear(); sessionStorage.clear(); });
afterEach(() => vi.restoreAllMocks());

describe('local greetings', () => {
  it.each([[5, 'morning'], [11, 'morning'], [12, 'afternoon'], [16, 'afternoon'], [17, 'evening'], [21, 'evening'], [22, 'night'], [4, 'night']])('uses the local hour %s for %s', (hour, period) => {
    expect(periodAt(Number(hour))).toBe(period);
  });
  it('reads the browser-local hour and retains the pair across refresh and daypart changes', () => {
    const first = sessionGreeting(new Date(2026, 9, 16, 9), () => 0);
    expect(first.period).toBe('morning');
    expect(sessionGreeting(new Date(2026, 9, 16, 23), () => 0.9)).toEqual(first);
    sessionStorage.clear();
    expect(sessionGreeting(new Date(2026, 9, 16, 23), () => 0.9).period).toBe('night');
  });
  it('renders names optionally without stray punctuation', () => {
    expect(greetingText({ period: 'morning', index: 0 }, '').title).toBe('Good morning.');
    expect(greetingText({ period: 'morning', index: 0 }, '  Ana  ').title).toBe('Good morning, Ana.');
    expect(greetingText({ period: 'night', index: 0 }, '').title).toBe('Still curious?');
  });
  it('bounds long names and strips control characters', () => {
    expect(normalizeName('  Ana\n  Smith  ')).toBe('Ana Smith');
    expect(Array.from(normalizeName('é'.repeat(100)))).toHaveLength(32);
  });
  it('ignores malformed session data', () => {
    sessionStorage.setItem('weave.greeting.v1', '{bad json');
    expect(sessionGreeting(new Date(2026, 9, 16, 13), () => 0).period).toBe('afternoon');
  });
  it('handles unavailable browser storage without throwing', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    expect(readPreference('name')).toBeNull();
    expect(() => writePreference('name', 'Ana')).not.toThrow();
    expect(sessionGreeting(new Date(2026, 9, 16, 18), () => 0).period).toBe('evening');
  });
});

describe('evidence dates', () => {
  it('uses explicit UTC, preserving date-only values', () => {
    expect(dateLabel('2026-05-11T09:00:00Z', true)).toBe('May 11, 2026 · 9:00 AM UTC');
    expect(dateLabel('2026-05-11')).toBe('May 11, 2026');
    expect(metadataLabel('2026-05-11T09:00:00Z')).toContain('UTC');
  });
  it('handles missing and invalid metadata and places unknown dates last', () => {
    expect(dateLabel('not-a-date')).toBe('Date not available');
    expect(dateLabel(null)).toBe('Date not available');
    expect(metadataLabel(null)).toBe('Not available');
    expect(timestampOrder(null)).toBeGreaterThan(timestampOrder('2026-05-11T09:00:00Z'));
  });
});
