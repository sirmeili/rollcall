// A Firebase service-account key file shaped like the real download: a fresh 2048-bit
// RSA key, pretty-printed with line breaks, about 2.4 KB. Test values only.

import { generateKeyPairSync } from "node:crypto";

export const SERVICE_ACCOUNT_EMAIL =
  "firebase-adminsdk-abc12@rollcall-test.iam.gserviceaccount.com";

/** The name Firebase gives the download: the project ID and the key's ID. */
export const SERVICE_ACCOUNT_FILE = "rollcall-test-0123456789ab.json";

export function serviceAccountKey(): string {
  const { privateKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
    privateKeyEncoding: { type: "pkcs8", format: "pem" },
    publicKeyEncoding: { type: "spki", format: "pem" },
  });
  const body = {
    type: "service_account",
    project_id: "rollcall-test",
    private_key_id: "0123456789abcdef0123456789abcdef01234567",
    private_key: privateKey,
    client_email: SERVICE_ACCOUNT_EMAIL,
    client_id: "123456789012345678901",
    auth_uri: "https://accounts.google.com/o/oauth2/auth",
    token_uri: "https://oauth2.googleapis.com/token",
  };
  return `${JSON.stringify(body, null, 2)}\n`;
}
