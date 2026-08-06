import { ArrowDown } from "lucide-react";
import { SourceTile } from "../components/brand";
import { Card } from "../components/ui";
import { cx } from "../lib/cx";
import { MEMORIES } from "../lib/data";

/**
 * Decisions ordered newest-first, with supersession drawn as an explicit
 * chain. This is the view that answers "what do we actually believe now,
 * and what did it replace?" — the thing a plain search over documents
 * cannot show.
 */
export default function Timeline() {
	const decisions = MEMORIES.filter((m) => m.tier === "decision");

	return (
		<>
			<div className="border-b border-line px-6 py-5 sm:px-8">
				<h1 className="display text-xl text-ink">Decision timeline</h1>
				<p className="mt-1 text-[13px] text-ink-2">
					What was decided, when, and what it replaced. Superseded entries stay
					visible so agents never resurface a reversed call.
				</p>
			</div>

			<div className="mx-auto max-w-3xl px-6 py-8 sm:px-8">
				<ol className="relative space-y-4 border-l border-line pl-6">
					{decisions.map((m) => {
						const dead = Boolean(m.supersededBy);
						return (
							<li key={m.id} className="relative">
								<span
									className={cx(
										"absolute -left-[27px] top-5 size-2.5 rounded-full ring-4 ring-[var(--canvas)]",
										dead ? "bg-ink-3" : "bg-decision",
									)}
								/>
								<Card className={cx("p-4", dead && "opacity-55")}>
									<div className="flex items-start gap-3">
										<SourceTile id={m.source} size={30} />
										<div className="min-w-0 flex-1">
											<h3
												className={cx(
													"text-sm font-semibold text-ink",
													dead && "line-through decoration-ink-3",
												)}
											>
												{m.title}
											</h3>
											<p className="mt-1 text-[13px] leading-relaxed text-ink-2">
												{m.body}
											</p>
											<p className="mt-2 text-2xs text-ink-3">
												{m.sourceLabel} · {m.updated}
											</p>
										</div>
									</div>
								</Card>

								{m.supersedes && (
									<div className="flex items-center gap-1.5 py-2 pl-1 text-2xs text-decision">
										<ArrowDown size={12} />
										replaces the decision below
									</div>
								)}
							</li>
						);
					})}
				</ol>
			</div>
		</>
	);
}
