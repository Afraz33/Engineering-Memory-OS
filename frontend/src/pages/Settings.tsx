import axios from "axios";
import { Check, Copy, HardDrive } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Card, Field, SectionTitle, StatusDot } from "../components/ui";
import { cx } from "../lib/cx";
import { useSession } from "../lib/session";
import { TIERS, TIER_META } from "../lib/types";

type Health = Record<string, boolean> | null;

export default function Settings() {
	const { session, patch } = useSession();
	const [health, setHealth] = useState<Health>(null);
	const [failed, setFailed] = useState(false);
	const [copied, setCopied] = useState(false);

	useEffect(() => {
		axios
			.get("http://localhost:8000/api/health")
			.then(({ data }) => setHealth(data))
			.catch(() => setFailed(true));
	}, []);

	const endpoint = `memory-os://${session.workspace.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "my-workspace"}`;

	return (
		<>
			<div className="border-b border-line px-6 py-5 sm:px-8">
				<h1 className="display text-xl text-ink">Settings</h1>
				<p className="mt-1 text-[13px] text-ink-2">
					Workspace, capture policy and runtime.
				</p>
			</div>

			<div className="mx-auto max-w-2xl space-y-8 px-6 py-6 sm:px-8">
				<Card className="space-y-5 p-5">
					<SectionTitle title="Workspace" />
					<Field
						label="Name"
						value={session.workspace}
						onChange={(e) => patch({ workspace: e.target.value })}
					/>
					<div>
						<span className="block text-[13px] font-medium text-ink-2">
							Agent endpoint
						</span>
						<div className="mt-1.5 flex items-center gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2">
							<code className="flex-1 truncate font-mono text-[13px] text-ink">
								{endpoint}
							</code>
							<Button
								size="sm"
								variant="ghost"
								onClick={() => {
									navigator.clipboard?.writeText(endpoint);
									setCopied(true);
									window.setTimeout(() => setCopied(false), 1500);
								}}
							>
								{copied ? <Check size={13} /> : <Copy size={13} />}
							</Button>
						</div>
					</div>
				</Card>

				<Card className="space-y-4 p-5">
					<SectionTitle
						title="Capture policy"
						description="Which tiers are written when a source syncs."
					/>
					<div className="space-y-2">
						{TIERS.map((t) => {
							const on = session.tiers.includes(t);
							return (
								<button
									key={t}
									type="button"
									onClick={() =>
										patch({
											tiers: on
												? session.tiers.filter((x) => x !== t)
												: [...session.tiers, t],
										})
									}
									className="flex w-full items-center gap-3 rounded-lg border border-line px-3 py-2.5 text-left transition-colors hover:bg-surface-2"
								>
									<span
										className="size-2 shrink-0 rounded-full"
										style={{ background: `var(--tier-${t})` }}
									/>
									<span className="min-w-0 flex-1">
										<span className="block text-[13px] font-medium text-ink">
											{TIER_META[t].label}
										</span>
										<span className="block text-2xs text-ink-3">
											{TIER_META[t].retention}
										</span>
									</span>
									<span
										className={cx(
											"flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors",
											on ? "bg-brand" : "bg-surface-3",
										)}
									>
										<span
											className={cx(
												"size-4 rounded-full bg-[var(--surface)] transition-transform",
												on && "translate-x-4",
											)}
										/>
									</span>
								</button>
							);
						})}
					</div>
				</Card>

				<Card className="space-y-4 p-5">
					<SectionTitle
						title="Runtime"
						description="Where the index and embeddings live."
					/>
					<div className="flex items-center gap-3 rounded-lg border border-line bg-surface-2 px-3 py-2.5">
						<HardDrive size={16} className="text-brand" />
						<span className="flex-1 text-[13px] text-ink">
							{session.deployment === "local" ? "Local" : "Hosted"}
						</span>
						<Button
							size="sm"
							variant="secondary"
							onClick={() =>
								patch({
									deployment: session.deployment === "local" ? "cloud" : "local",
								})
							}
						>
							Switch
						</Button>
					</div>

					<div className="space-y-2">
						{failed ? (
							<p className="text-2xs text-danger">
								API unreachable at localhost:8000 — start the backend.
							</p>
						) : (
							Object.entries(health ?? { server: false, database: false }).map(
								([svc, ok]) => (
									<div
										key={svc}
										className="flex items-center gap-2.5 text-[13px] text-ink-2"
									>
										<StatusDot
											status={health === null ? "idle" : ok ? "connected" : "error"}
										/>
										<span className="flex-1 capitalize">{svc}</span>
										<span className="font-mono text-2xs text-ink-3">
											{health === null ? "checking" : ok ? "ok" : "down"}
										</span>
									</div>
								),
							)
						)}
					</div>
				</Card>
			</div>
		</>
	);
}
