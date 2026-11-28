/** Comparing the phone app's release with the server's (ADR-0025). */

const RELEASE = /^(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$/;

/** A release version as numbers to compare, a final release after all its candidates; null
 * for a development build (`dev`, `dev (<short commit>)`). */
function parts(version: string): number[] | null {
  const match = RELEASE.exec(version);
  if (!match) return null;
  const [, major, minor, patch, candidate] = match;
  return [major, minor, patch].map(Number).concat(candidate ? Number(candidate) : Infinity);
}

/** Which of the two is on the older release, or null when they match or either is a
 * development build. */
export function olderPart(app: string, server: string): "app" | "server" | null {
  const a = parts(app);
  const s = parts(server);
  if (!a || !s) return null;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== s[i]) return a[i] < s[i] ? "app" : "server";
  }
  return null;
}
