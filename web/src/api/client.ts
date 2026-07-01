import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { toApiError } from "./errors";

// Same-origin baseUrl: in dev, Vite proxies the API prefixes to FastAPI; in prod,
// the SPA is served by FastAPI itself. credentials:"include" sends the httpOnly
// session cookie on every request (there is no bearer token).
export const api = createClient<paths>({
  baseUrl: "/",
  credentials: "include",
});

// Thin helpers that unwrap openapi-fetch's { data, error } and throw ApiError on
// failure, so query/mutation functions can `return unwrap(await api.GET(...))`.
type Result<T> = { data?: T; error?: unknown; response: Response };

export function unwrap<T>({ data, error, response }: Result<T>): T {
  if (error !== undefined || !response.ok) {
    throw toApiError(error, response);
  }
  return data as T;
}
