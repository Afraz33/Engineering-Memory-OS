import { Plug, RefreshCw, TriangleAlert } from "lucide-react";
import { SourceTile } from "../components/brand";
import { Button, Card, StatusDot, SectionTitle } from "../components/ui";
import { cx } from "../lib/cx";
import { CONNECTIONS, KIND_LABEL, SOURCES, SOURCE_BY_ID } from "../lib/data";

export default function Sources() {
	const connectedIds = new Set(CONNECTIONS.map((c) => c.id));
	const available = SOURCES.filter((s) => !connectedIds.has(s.id));

	return (
		<>
			<div className="border-b border-line px-6 py-5 sm:px-8">
				<h1 className="display text-xl text-ink">Sources</h1>
				<p className="mt-1 text-[13px] text-ink-2">
					Memory OS reads these. You never write a log entry by hand.
				</p>
			</div>

			<div className="mx-auto max-w-4xl space-y-8 px-6 py-6 sm:px-8">
				<section className="space-y-3">
					<SectionTitle
						title="Connected"
						description={`${CONNECTIONS.length} sources feeding this workspace.`}
					/>

					{CONNECTIONS.map((c) => {
						const def = SOURCE_BY_ID[c.id];
						const failing = c.status === "error";
						return (
							<Card
								key={c.id}
								className={cx("flex flex-wrap items-center gap-4 p-4", failing && "border-danger/35")}
							>
								<SourceTile id={c.id} size={40} />

								<div className="min-w-0 flex-1">
									<div className="flex items-center gap-2">
										<span className="text-sm font-medium text-ink">{def.name}</span>
										<StatusDot status={c.status} />
										<span className="text-2xs capitalize text-ink-3">{c.status}</span>
									</div>
									<p className="mt-0.5 text-2xs text-ink-3">{def.captures}</p>
								</div>

								<div className="text-right">
									<div className="font-mono text-[13px] text-ink">
										{c.items.toLocaleString()}
									</div>
									<div className="text-2xs text-ink-3">{c.lastSync}</div>
								</div>

								{failing ? (
									<Button size="sm" variant="danger">
										<TriangleAlert size={13} />
										Reauthorize
									</Button>
								) : (
									<Button size="sm" variant="secondary">
										<RefreshCw size={13} />
										Sync
									</Button>
								)}
							</Card>
						);
					})}
				</section>

				<section className="space-y-3">
					<SectionTitle
						title="Available"
						description="Connect more surfaces to widen the shared context."
					/>

					<div className="grid gap-3 sm:grid-cols-2">
						{available.map((s) => (
							<Card key={s.id} interactive className="flex items-start gap-3 p-4">
								<SourceTile id={s.id} size={36} muted={!s.available} />
								<div className="min-w-0 flex-1">
									<div className="flex items-center gap-2">
										<span className="text-sm font-medium text-ink">{s.name}</span>
										<span className="rounded border border-line px-1.5 py-px text-2xs text-ink-3">
											{KIND_LABEL[s.kind]}
										</span>
									</div>
									<p className="mt-1 text-2xs leading-relaxed text-ink-3">
										{s.available ? s.captures : "Coming soon"}
									</p>
								</div>
								<Button size="sm" variant="secondary" disabled={!s.available}>
									<Plug size={13} />
									Connect
								</Button>
							</Card>
						))}
					</div>
				</section>
			</div>
		</>
	);
}
