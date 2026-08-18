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

/**
 * One row of the capture audit feed. Identical for every connector — the
 * backend writes them all to the same `source_events` table — so the Jira card
 * renders the same shape the Slack card does.
 */
export interface SourceActivityItem {
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

/** @deprecated Use SourceActivityItem — kept so existing imports still resolve. */
export type SlackActivityItem = SourceActivityItem;

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
): Promise<SourceActivityItem[]> {
	const { data } = await api.get<SourceActivityItem[]>("/api/slack/activity", {
		params: { limit },
	});
	return data;
}

/* ── Jira connector ────────────────────────────────────────────────── */

export interface JiraStatus {
	/** Whether the *server* has Atlassian credentials at all. False means no
	 * amount of clicking Connect will work — it is a backend .env problem. */
	configured: boolean;
	connected: boolean;
	site_name: string | null;
	site_url: string | null;
	installed_at: string | null;
	last_synced_at: string | null;
	/** Whether the dynamic webhook registration went through. When false, Jira
	 * refused it and the user has to paste `webhook_url` into Jira by hand —
	 * without this flag that failure is invisible until nothing ever arrives. */
	webhook_active: boolean;
	webhook_url: string | null;
	/** Issues and comments Jira delivered to us. */
	received: number;
	/** …of which the classifier turned into memories. */
	stored: number;
	quarantined: number;
	/** …dropped by the pre-filter or the classifier. Expected to dominate. */
	dropped: number;
	last_event_at: string | null;
}

export interface JiraSyncResult {
	queued: number;
	skipped: number;
	reason: string;
}

export async function fetchJiraStatus(): Promise<JiraStatus> {
	const { data } = await api.get<JiraStatus>("/api/jira/status");
	return data;
}

/**
 * Starts the connection. Built server-side because the URL carries a signed
 * `state` token — the browser has nothing to sign with.
 */
export async function fetchJiraInstallUrl(): Promise<string> {
	const { data } = await api.get<{ url: string }>("/api/jira/install");
	return data.url;
}

export async function disconnectJira(): Promise<void> {
	await api.delete("/api/jira/disconnect");
}

export async function fetchJiraActivity(
	limit = 25,
): Promise<SourceActivityItem[]> {
	const { data } = await api.get<SourceActivityItem[]>("/api/jira/activity", {
		params: { limit },
	});
	return data;
}

/**
 * Backfill: pull recently-updated issues through the capture pipeline.
 * Webhooks only cover what happens after connecting, so without this the first
 * hour of the integration shows an empty feed.
 */
export async function syncJira(): Promise<JiraSyncResult> {
	const { data } = await api.post<JiraSyncResult>("/api/jira/sync");
	return data;
}

/* ── Workspace ──────────────────────────────────────────────────────── */

export interface WorkspaceMember {
	user_id: string;
	email: string;
	name: string | null;
	role: "owner" | "member";
}

export interface Workspace {
	id: string;
	name: string;
	role: "owner" | "member";
	members: WorkspaceMember[];
}

/** Resolves to null before onboarding: a first-time user has no workspace yet. */
export async function fetchWorkspace(): Promise<Workspace | null> {
	try {
		const { data } = await api.get<Workspace>("/api/workspaces/me");
		return data;
	} catch {
		return null;
	}
}

/** The onboarding flow's "name your workspace" step — the only place a
 * workspace gets created. Safe to call again later; it no-ops if one already
 * exists. */
export async function createWorkspace(name: string): Promise<Workspace> {
	const { data } = await api.post<Workspace>("/api/workspaces", { name });
	return data;
}

export async function renameWorkspace(name: string): Promise<Workspace> {
	const { data } = await api.patch<Workspace>("/api/workspaces/me", { name });
	return data;
}

export async function inviteToWorkspace(
	email: string,
): Promise<{ status: "joined" | "invited"; user_id: string | null }> {
	const { data } = await api.post("/api/workspaces/invite", { email });
	return data;
}

export async function removeWorkspaceMember(userId: string): Promise<void> {
	await api.delete(`/api/workspaces/members/${userId}`);
}

export interface WorkspaceSummary {
	id: string;
	name: string;
	role: "owner" | "member";
	active: boolean;
}

/** Every workspace the caller belongs to, for the workspace switcher. */
export async function fetchWorkspaces(): Promise<WorkspaceSummary[]> {
	const { data } = await api.get<WorkspaceSummary[]>("/api/workspaces");
	return data;
}

export async function switchWorkspace(workspaceId: string): Promise<Workspace> {
	const { data } = await api.post<Workspace>("/api/workspaces/switch", {
		workspace_id: workspaceId,
	});
	return data;
}
