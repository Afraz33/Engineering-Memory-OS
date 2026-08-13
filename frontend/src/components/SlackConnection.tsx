import { Link2Off, Plug, RefreshCw, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
	disconnectSlack,
	fetchSlackActivity,
	fetchSlackInstallUrl,
	fetchSlackStatus,
	type SlackActivityItem,
	type SlackStatus,
} from "../lib/api";
import { cx } from "../lib/cx";
import { useWorkspace } from "../lib/workspace-context";
import { SourceTile } from "./brand";
import { Button, Card, SectionTitle, StatusDot } from "./ui";

/**
 * The one source that is actually wired to the backend.
 *
 * Everything else on the Sources page is still fixture data; this card talks to
 * /api/slack. Deliberately shows the drop count next to the stored count —
 * capture is supposed to reject most of what it sees, and a UI that only
 * surfaced "stored" would make a working pre-filter look like a broken sync.
 */

const OUTCOME_TONE: Record<string, string> = {
	stored: "text-ok border-ok/30 bg-ok/10",
	quarantined: "text-warn border-warn/30 bg-warn/10",
	error: "text-danger border-danger/30 bg-danger/10",
	pending: "text-ink-3 border-line bg-surface-2",
};

const OUTCOME_LABEL: Record<string, string> = {
	stored: "stored",
	quarantined: "quarantined",
	dropped_prefilter: "filtered",
	dropped_classifier: "not durable",
	pending: "processing",
	error: "failed",
};

function OutcomeBadge({ outcome }: { outcome: string }) {
	return (
		<span
			className={cx(
				"shrink-0 rounded border px-1.5 py-px text-2xs",
				OUTCOME_TONE[outcome] ?? "text-ink-3 border-line bg-surface-2",
			)}
		>
			{OUTCOME_LABEL[outcome] ?? outcome}
		</span>
	);
}

function Stat({ label, value }: { label: string; value: number }) {
	return (
		<div>
			<div className="font-mono text-[13px] text-ink">
				{value.toLocaleString()}
			</div>
			<div className="text-2xs text-ink-3">{label}</div>
		</div>
	);
}

export default function SlackConnection() {
	const { workspace } = useWorkspace();
	const isOwner = workspace?.role === "owner";
	const [status, setStatus] = useState<SlackStatus | null>(null);
	const [activity, setActivity] = useState<SlackActivityItem[]>([]);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [params, setParams] = useSearchParams();

	const refresh = useCallback(async () => {
		try {
			const next = await fetchSlackStatus();
			setStatus(next);
			setActivity(next.connected ? await fetchSlackActivity(15) : []);
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
		const result = params.get("slack");
		if (!result) return;
		if (result === "error") {
			setError(`Slack install failed (${params.get("reason") ?? "unknown"}).`);
		}
		params.delete("slack");
		params.delete("reason");
		setParams(params, { replace: true });
	}, [params, setParams]);

	const connect = async () => {
		setBusy(true);
		setError(null);
		try {
			// Full navigation, not a popup: Slack's consent screen refuses to be
			// framed, and a popup here is what ad blockers eat.
			window.location.href = await fetchSlackInstallUrl();
		} catch {
			setError("Slack is not configured on the server.");
			setBusy(false);
		}
	};

	const disconnect = async () => {
		setBusy(true);
		try {
			await disconnectSlack();
			await refresh();
		} finally {
			setBusy(false);
		}
	};

	if (!status) {
		return (
			<Card className="flex items-center gap-3 p-4">
				<div className="size-4 animate-spin rounded-full border-2 border-line border-t-brand" />
				<span className="text-[13px] text-ink-2">Checking Slack…</span>
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
				<SourceTile id="slack" size={40} muted={!status.connected} />

				<div className="min-w-0 flex-1">
					<div className="flex items-center gap-2">
						<span className="text-sm font-medium text-ink">Slack</span>
						<StatusDot status={status.connected ? "connected" : "idle"} />
						<span className="text-2xs text-ink-3">
							{status.connected
								? (status.team_name ?? "connected")
								: "not connected"}
						</span>
					</div>
					<p className="mt-0.5 text-2xs text-ink-3">
						{status.connected
							? "Reading channels the bot was invited to."
							: "Channel threads where choices get argued out."}
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
					<span className="text-2xs text-ink-3">Ask an owner to connect Slack.</span>
				)}
			</Card>

			{unconfigured && (
				<p className="flex items-start gap-2 text-2xs text-warn">
					<TriangleAlert size={13} className="mt-px shrink-0" />
					Slack credentials are missing on the server. Set SLACK_CLIENT_ID,
					SLACK_CLIENT_SECRET and SLACK_SIGNING_SECRET in backend/.env.
				</p>
			)}

			{error && (
				<p className="flex items-start gap-2 text-2xs text-danger">
					<TriangleAlert size={13} className="mt-px shrink-0" />
					{error}
				</p>
			)}

			{status.connected && (
				<Card className="p-4">
					<SectionTitle
						title="Recent activity"
						description="Every message that arrived, and what capture decided about it."
					/>
					{activity.length === 0 ? (
						<p className="mt-3 text-2xs text-ink-3">
							Nothing yet. Invite the bot to a channel with{" "}
							<code className="rounded bg-surface-2 px-1">/invite @Memory OS</code>{" "}
							and post something worth remembering.
						</p>
					) : (
						<ul className="mt-3 divide-y divide-line">
							{activity.map((item) => (
								<li key={item.id} className="flex items-start gap-3 py-2.5">
									<OutcomeBadge outcome={item.outcome} />
									<div className="min-w-0 flex-1">
										<p className="truncate text-[13px] text-ink">
											{item.memory_title ?? item.text ?? "(no text)"}
										</p>
										<p className="mt-0.5 truncate text-2xs text-ink-3">
											{item.author ?? "unknown"}
											{item.reason ? ` · ${item.reason}` : ""}
										</p>
									</div>
								</li>
							))}
						</ul>
					)}
				</Card>
			)}
		</div>
	);
}
