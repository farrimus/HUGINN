// Module-level cache — fetched once per page load, shared across all consumers.
let cachedNames: string[] | null = null;
let fetchPromise: Promise<void> | null = null;

function fetchNames(apiBaseUrl: string): Promise<void> {
  if (fetchPromise) return fetchPromise;
  fetchPromise = fetch(`${apiBaseUrl}/systems/names`)
    .then(r => r.json())
    .then(data => { cachedNames = data.names as string[]; })
    .catch(() => { fetchPromise = null; }); // allow retry on failure
  return fetchPromise;
}

export function useSystemNames(apiBaseUrl: string) {
  // Kick off fetch immediately (no-op if already in flight or done).
  fetchNames(apiBaseUrl);

  function search(query: string): string[] {
    if (!cachedNames || query.length < 2) return [];
    const q = query.toLowerCase();
    const prefix: string[] = [];
    const substr: string[] = [];
    for (const name of cachedNames) {
      if (prefix.length + substr.length >= 10) break; // collect a bit extra for dedup
      if (name.startsWith(q)) prefix.push(name);
      else if (name.includes(q)) substr.push(name);
    }
    return [...prefix, ...substr].slice(0, 5);
  }

  return { search, ready: cachedNames !== null };
}
