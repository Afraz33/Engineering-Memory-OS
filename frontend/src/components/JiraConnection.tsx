import {
	Check,
	Copy,
	DownloadCloud,
	Link2Off,
	Plug,
	RefreshCw,
	TriangleAlert,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
	disconnectJira,
	fetchJiraActivity,
	fetchJiraInstallUrl,
	fetchJiraStatus,
	syncJira,
	type JiraStatus,
	type SourceActivityItem,
} from "../lib/api";
import { cx } from "../lib/cx";
import { useWorkspace } from "../lib/workspace-context";
import { SourceTile } from "./brand";
import { ActivityFeed, Stat } from "./SourceActivity";
import { Button, Card, StatusDot } from "./ui";

/**
 * Jira, wired to /api/jira. Structurally the twin of SlackConnection, with two
 * differences that come straight from how Jira works:
 *
 *  - **Backfill.** Webhooks only cover what happens after connecting, and the
 *    decisions worth remembering are already in the backlog. Hence "Sync".
 *  - **Webhook fallback.** Atlassian refuses to register a dynamic webhook
 *    unless the URL sits under the app's configured base URL, which is easy to
 *    get wrong in dev. When that happens the connection still succeeds, so the
 *    only way the user finds out is this card telling them.
 */

/** Why the OAuth callback bounced, in words a user can act on. */
const ERROR_REASON: Record<string, string> = {
	cancelled: "You declined the Atlassian consent screen.",
	bad_state: "The install link expired. Try connecting again.",
	exchange: "Atlassian rejected the token exchange. Check JIRA_CLIENT_SECRET.",
	no_site: "That Atlassian account has no Jira site we can read.",
	access_denied: "Atlassian denied the request.",
};

function WebhookHint({ url }: { url: string }) {
	const [copied, setCopied] = useState(false);

	const copy = async () => {
		await navigator.clipboard.writeText(url);
		setCopied(true);
		setTimeout(() => setCopied(false), 1500);
	};

	return (
		<Card className="space-y-2 border-warn/35 p-4">
			<p className="flex items-start gap-2 text-2xs text-warn">
				<TriangleAlert size={13} className="mt-px shrink-0" />
				Jira would not register the webhook automatically. Add it by hand:
				Jira Settings → System → WebHooks → Create, paste the URL below, and
				select the issue and comment events.
			</p>
			<div className="flex items-center gap-2">
				<code className="min-w-0 flex-1 truncate rounded bg-surface-2 px-2 py-1 text-2xs text-ink-2">
					{url}
				</code>
				<Button size="sm" variant="secondary" onClick={copy}>
					{copied ? <Check size={13} /> : <Copy size={13} />}
					{copied ? "Copied" : "Copy"}
				</Button>
			</div>
			<p className="text-2xs text-ink-3">
				Treat this URL as a secret — anyone holding it can post events into
				this workspace.
			</p>
		</Card>
	);
}

export default function JiraConnection() {
	const { workspace } = useWorkspace();
	const isOwner = workspace?.role === "owner";
	const [status, setStatus] = useState<JiraStatus | null>(null);
	const [activity, setActivity] = useState<SourceActivityItem[]>([]);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [note, setNote] = useState<string | null>(null);
	const [params, setParams] = useSearchParams();

	const refresh = useCallback(async () => {
		try {
			const next = await fetchJiraStatus();
			setStatus(next);
			setActivity(next.connected ? await fetchJiraActivity(15) : []);
		} catch {
			setError("Could not reach the server.");
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	// The OAuth callback redirects back here with the result in the query
	// string, since it is a full page navigation and no component state survives.
	useEffect(() => {
		const result = params.get("jira");
		if (!result) return;
		if (result === "error") {
			const reason = params.get("reason") ?? "unknown";
			setError(ERROR_REASON[reason] ?? `Jira connection failed (${reason}).`);
		}
		params.delete("jira");
		params.delete("reason");
		setParams(params, { replace: true });
	}, [params, setParams]);

	const connect = async () => {
		setBusy(true);
		setError(null);
		try {
			// Full navigation, not a popup: Atlassian's consent screen refuses to
			// be framed, and a popup here is what ad blockers eat.
			window.location.href = await fetchJiraInstallUrl();
		} catch {
			setError("Jira is not configured on the server.");
			setBusy(false);
		}
	};

	const disconnect = async () => {
		setBusy(true);
		try {
			await disconnectJira();
			await refresh();
		} finally {
			setBusy(false);
		}
	};

	const backfill = async () => {
		setBusy(true);
		setError(null);
		setNote(null);
		try {
			const result = await syncJira();
			// Queued, not stored: classification happens in the background, so the
			// honest thing to report is how many issues entered the pipeline.
			setNote(
				result.queued === 0
					? `Nothing new to pull — ${result.reason}.`
					: `Queued ${result.queued} issue${result.queued === 1 ? "" : "s"} for capture` +
						(result.skipped ? `, skipped ${result.skipped} already seen.` : "."),
			);
			await refresh();
		} catch {
			setError("Backfill failed. The Jira token may need reconnecting.");
		} finally {
			setBusy(false);
		}
	};

	if (!status) {
		return (
			<Card className="flex items-center gap-3 p-4">
				<div className="size-4 animate-spin rounded-full border-2 border-line border-t-brand" />
				<span className="text-[13px] text-ink-2">Checking Jira…</span>
			</Card>
		);
	}

	const unconfigured = !status.configured;

	return (
		<div className="space-y-3">
			<Card
				className={cx(
					"flex flex-wrap items-center gap-4 p-4",
					error && "border-danger/35",
				)}
			>
				<SourceTile id="jira" size={40} muted={!status.connected} />

				<div className="min-w-0 flex-1">
					<div className="flex items-center gap-2">
						<span className="text-sm font-medium text-ink">Jira</span>
						<StatusDot status={status.connected ? "connected" : "idle"} />
						<span className="text-2xs text-ink-3">
							{status.connected
								? (status.site_name ?? "connected")
								: "not connected"}
						</span>
					</div>
					<p className="mt-0.5 text-2xs text-ink-3">
						{status.connected
							? "Reading issue descriptions and comment threads."
							: "Issue descriptions and the comment threads that settle them."}
					</p>
				</div>

				{status.connected && (
					<div className="flex gap-5 pr-1">
						<Stat label="received" value={status.received} />
						<Stat label="stored" value={status.stored} />
						<Stat label="filtered" value={status.dropped} />
					</div>
				)}

				{status.connected ? (
					<div className="flex gap-2">
						<Button size="sm" variant="secondary" onClick={backfill} disabled={busy}>
							<DownloadCloud size={13} />
							Sync
						</Button>
						<Button size="sm" variant="secondary" onClick={refresh} disabled={busy}>
							<RefreshCw size={13} />
							Refresh
						</Button>
						{isOwner && (
							<Button size="sm" variant="danger" onClick={disconnect} disabled={busy}>
								<Link2Off size={13} />
								Disconnect
							</Button>
						)}
					</div>
				) : isOwner ? (
					<Button size="sm" onClick={connect} disabled={busy || unconfigured}>
						<Plug size={13} />
						{busy ? "Redirecting…" : "Connect"}
					</Button>
				) : (
					<span className="text-2xs text-ink-3">Ask an owner to connect Jira.</span>
				)}
			</Card>

			{unconfigured && (
				<p className="flex items-start gap-2 text-2xs text-warn">
					<TriangleAlert size={13} className="mt-px shrink-0" />
					Jira credentials are missing on the server. Set JIRA_CLIENT_ID and
					JIRA_CLIENT_SECRET in backend/.env.
				</p>
			)}

			{status.connected && !status.webhook_active && status.webhook_url && (
				<WebhookHint url={status.webhook_url} />
			)}

			{error && (
				<p className="flex items-start gap-2 text-2xs text-danger">
					<TriangleAlert size={13} className="mt-px shrink-0" />
					{error}
				</p>
			)}

			{note && <p className="text-2xs text-ink-3">{note}</p>}

			{status.connected && (
				<ActivityFeed
					items={activity}
					description="Every issue and comment that arrived, and what capture decided about it."
					empty={
						<>
							Nothing yet. Hit <strong>Sync</strong> to pull recently updated
							issues, or edit an issue description in Jira to test the webhook.
						</>
					}
				/>
			)}
		</div>
	);
}
