/** The server's health, which answers without signing in. */

import { api } from "#lib/api/client.ts";

export interface Health {
  status: string;
  /** The release the server is: `1.4.0`, `1.4.0-rc.1`, `dev (<short commit>)` or `dev`.
   * Servers before 1.4.0 leave it out. */
  version?: string;
}

/** The server's version, or null when it cannot be reached or doesn't say. */
export async function serverVersion(): Promise<string | null> {
  try {
    return (await api<Health>("/health")).version ?? null;
  } catch {
    return null;
  }
}
