import type { SourceActivityItem } from "../lib/api";
import { cx } from "../lib/cx";
import { Card, SectionTitle } from "./ui";

/**
 * The capture audit feed, shared by every connector card.
 *
 * Deliberately shows drops next to stores — capture is *supposed* to reject
 * most of what it sees, and a UI that only surfaced "stored" would make a
 * working pre-filter look like a broken sync.
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

export function OutcomeBadge({ outcome }: { outcome: string }) {
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

export function Stat({ label, value }: { label: string; value: number }) {
	return (
		<div>
			<div className="font-mono text-[13px] text-ink">
				{value.toLocaleString()}
			</div>
			<div className="text-2xs text-ink-3">{label}</div>
		</div>
	);
}

export function ActivityFeed({
	items,
	description,
	empty,
}: {
	items: SourceActivityItem[];
	description: string;
	/** What to tell the user when nothing has arrived — connector-specific,
	 * because the fix is too ("invite the bot" vs "check the webhook"). */
	empty: React.ReactNode;
}) {
	return (
		<Card className="p-4">
			<SectionTitle title="Recent activity" description={description} />
			{items.length === 0 ? (
				<p className="mt-3 text-2xs text-ink-3">{empty}</p>
			) : (
				<ul className="mt-3 divide-y divide-line">
					{items.map((item) => (
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
	);
}
