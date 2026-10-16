export function shortId(id: string) { return id.slice(id.indexOf(':') + 1); }

export function dateLabel(timestamp: string | null, withTime = false) {
  if (!timestamp) return 'Date not available';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return 'Date not available';
  const day = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
  return withTime && timestamp.includes('T') ? `${day} · ${date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'UTC' })} UTC` : day;
}

export function metadataLabel(value: unknown) {
  if (value == null || value === '') return 'Not available';
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}(T|$)/.test(value)) return dateLabel(value, true);
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

export function timestampOrder(timestamp: string | null) {
  const value = timestamp ? Date.parse(timestamp) : NaN;
  return Number.isNaN(value) ? Number.MAX_SAFE_INTEGER : value;
}
