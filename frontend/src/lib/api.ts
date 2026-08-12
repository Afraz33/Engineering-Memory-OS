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

/* ── Slack connector ───────────────────────────────────────────────── */

export interface SlackStatus {
	/** Whether the *server* has Slack credentials at all. False means no amount
	 * of clicking Connect will work — it is a backend .env problem. */
	configured: boolean;
	connected: boolean;
	team_name: string | null;
	team_id: string | null;
	installed_at: string | null;
	/** Messages Slack delivered to us. */
	received: number;
	/** …of which the classifier turned into memories. */
	stored: number;
	quarantined: number;
	/** …dropped by the pre-filter or the classifier. Expected to dominate. */
	dropped: number;
	last_event_at: string | null;
}

export interface SlackActivityItem {
	id: string;
	author: string | null;
	text: string | null;
	outcome: string;
	reason: string | null;
	occurred_at: string | null;
	memory_id: string | null;
	memory_title: string | null;
	memory_type: string | null;
}

export async function fetchSlackStatus(): Promise<SlackStatus> {
	const { data } = await api.get<SlackStatus>("/api/slack/status");
	return data;
}

/**
 * Starts the install. The URL is built server-side because it carries a signed
 * `state` token — the browser has nothing to sign with.
 */
export async function fetchSlackInstallUrl(): Promise<string> {
	const { data } = await api.get<{ url: string }>("/api/slack/install");
	return data.url;
}

export async function disconnectSlack(): Promise<void> {
	await api.delete("/api/slack/disconnect");
}

export async function fetchSlackActivity(
	limit = 25,
): Promise<SlackActivityItem[]> {
	const { data } = await api.get<SlackActivityItem[]>("/api/slack/activity", {
		params: { limit },
	});
	return data;
}
