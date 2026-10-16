import { useCallback, useState } from 'react';

export function readPreference(key: string) {
  try { return localStorage.getItem(key); } catch { return null; }
}
export function writePreference(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* Preference remains usable in memory. */ }
}
export function useSidebarPreference(side: 'left' | 'right') {
  const key = `weave.sidebar.${side}`;
  const [collapsed, setCollapsed] = useState(() => readPreference(key) === 'collapsed');
  const update = useCallback((value: boolean) => {
    setCollapsed(value); writePreference(key, value ? 'collapsed' : 'expanded');
  }, [key]);
  return [collapsed, update] as const;
}

export function normalizeName(value: string) {
  return Array.from(value.replace(/[\p{Cc}\p{Cf}]/gu, '').trim().replace(/\s+/g, ' ')).slice(0, 32).join('');
}

export const NAME_KEY = 'weave.preferredName';
const GREETING_KEY = 'weave.greeting.v1';
const PAIRS = {
  morning: [ ['Good morning', 'What shall we untangle today?'], ['Morning', 'Ready to connect the dots?'] ],
  afternoon: [ ['Good afternoon', "Let's follow the evidence."], ['Ready for a little clarity', 'What would you like to understand?'] ],
  evening: [ ['Good evening', 'Every connection tells a story.'], ["What's on your mind", 'What shall we explore tonight?'] ],
  night: [ ['Still curious', "Let's trace the story behind it."], ['Working late', "Let's untangle something."] ],
} as const;
type Period = keyof typeof PAIRS;
export type Greeting = { period: Period; index: number };

export function periodAt(hour: number): Period {
  return hour >= 5 && hour < 12 ? 'morning' : hour >= 12 && hour < 17 ? 'afternoon' : hour >= 17 && hour < 22 ? 'evening' : 'night';
}
export function sessionGreeting(now = new Date(), random = Math.random): Greeting {
  try {
    const saved = JSON.parse(sessionStorage.getItem(GREETING_KEY) ?? 'null') as Greeting | null;
    if (saved && Object.hasOwn(PAIRS, saved.period) && Number.isInteger(saved.index) && saved.index >= 0 && saved.index < PAIRS[saved.period].length) return saved;
  } catch { /* Restricted or corrupt storage: choose once for this mounted app. */ }
  const greeting = { period: periodAt(now.getHours()), index: Math.floor(random() * 2) };
  try { sessionStorage.setItem(GREETING_KEY, JSON.stringify(greeting)); } catch { /* No persistence available. */ }
  return greeting;
}
export function greetingText(greeting: Greeting, preferredName: string) {
  const pair = PAIRS[greeting.period]?.[greeting.index];
  if (!pair) return { title: 'Hello there.', subtitle: 'What shall we untangle today?' };
  const name = normalizeName(preferredName);
  const question = greeting.period === 'night' || greeting.index === 1 && greeting.period !== 'morning';
  return { title: `${pair[0]}${name ? `, ${name}` : ''}${question ? '?' : '.'}`, subtitle: pair[1] };
}
