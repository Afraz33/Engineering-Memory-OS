import axios from "axios";

/**
 * Shared API client.
 *
 * `withCredentials` is the load-bearing setting: the auth cookie is HttpOnly
 * and cross-origin in dev (5173 → 8000), so without it the browser neither
 * stores the cookie on login nor sends it on subsequent calls.
 */
export const api = axios.create({
	baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
	withCredentials: true,
});

export interface User {
	id: string;
	email: string;
	name: string | null;
	avatar_url: string | null;
}

export async function loginWithGoogle(credential: string): Promise<User> {
	const { data } = await api.post<User>("/api/auth/google", { credential });
	return data;
}

/** Resolves to null when the cookie is missing or the token has expired. */
export async function fetchMe(): Promise<User | null> {
	try {
		const { data } = await api.get<User>("/api/auth/me");
		return data;
	} catch {
		return null;
	}
}

export async function logout(): Promise<void> {
	await api.post("/api/auth/logout");
}
