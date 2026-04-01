/**
 * Sanitizes a user search query into a valid PostgreSQL tsquery string.
 *
 * Rules:
 * - Splits on whitespace, joins with & (AND semantics)
 * - Strips non-alphanumeric characters (keeps accented chars)
 * - Converts "quoted phrases" to <-> (FOLLOWED BY operator for phrase search)
 * - Returns null if nothing remains after sanitization
 */
export function sanitizeSearchQuery(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  const parts: string[] = [];

  // Extract quoted phrases first
  const withoutPhrases = trimmed.replace(/"([^"]+)"/g, (_match, phrase: string) => {
    const words = phrase
      .split(/\s+/)
      .map((w) => w.replace(/[^a-zA-Z0-9À-ÿ]/g, ''))
      .filter(Boolean);
    if (words.length > 0) {
      parts.push(words.join(' <-> '));
    }
    return '';
  });

  const remainingWords = withoutPhrases
    .split(/\s+/)
    .map((w) => w.replace(/[^a-zA-Z0-9À-ÿ]/g, ''))
    .filter(Boolean);

  parts.push(...remainingWords);

  if (parts.length === 0) return null;
  return parts.join(' & ');
}
