import { ArrowUpRight, Filter, GitCommitHorizontal, Info } from "lucide-react";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { SourceTile } from "../components/brand";
import { Card, TierBadge } from "../components/ui";
import { cx } from "../lib/cx";
import { MEMORIES, MEMORY_BY_ID, SOURCE_BY_ID, SPACES } from "../lib/data";
import { TIERS, TIER_META, type Tier } from "../lib/types";

function PageHeader({
	title,
	description,
	right,
}: {
	title: string;
	description: string;
	right?: React.ReactNode;
}) {
	return (
		<div className="flex flex-wrap items-end justify-between gap-4 border-b border-line px-6 py-5 sm:px-8">
			<div>
				<h1 className="display text-xl text-ink">{title}</h1>
				<p className="mt-1 text-[13px] text-ink-2">{description}</p>
			</div>
			{right}
		</div>
	);
}

function MemoryCard({ id }: { id: string }) {
	const m = MEMORY_BY_ID[id];
	const superseded = Boolean(m.supersededBy);
	const replaced = m.supersedes ? MEMORY_BY_ID[m.supersedes] : undefined;

	return (
		<Card
			interactive
			className={cx("p-5", superseded && "opacity-60")}
		>
			<div className="flex items-start gap-3">
				<SourceTile id={m.source} size={34} />

				<div className="min-w-0 flex-1">
					<div className="flex flex-wrap items-center gap-2">
						<TierBadge tier={m.tier} size="sm" />
						{superseded && (
							<span className="rounded-md border border-line bg-surface-2 px-1.5 py-0.5 text-2xs text-ink-3 line-through">
								superseded
							</span>
						)}
						<span className="ml-auto font-mono text-2xs text-ink-3">
							{Math.round(m.confidence * 100)}%
						</span>
					</div>

					<h3
						className={cx(
							"mt-2 text-[15px] font-semibold leading-snug text-ink",
							superseded && "line-through decoration-ink-3",
						)}
					>
						{m.title}
					</h3>

					<p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">{m.body}</p>

					{replaced && (
						<div className="mt-3 flex items-start gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2">
							<GitCommitHorizontal size={13} className="mt-0.5 shrink-0 text-decision" />
							<p className="text-2xs leading-relaxed text-ink-2">
								Replaces{" "}
								<span className="text-ink line-through decoration-ink-3">
									{replaced.title}
								</span>{" "}
								— {replaced.sourceLabel}, {replaced.updated}.
							</p>
						</div>
					)}

					<div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs text-ink-3">
						<a
							href="#source"
							className="inline-flex items-center gap-1 text-ink-2 underline-offset-4 hover:text-ink hover:underline"
						>
							{m.sourceLabel}
							<ArrowUpRight size={11} />
						</a>
						<span>·</span>
						<span>{SOURCE_BY_ID[m.source].name}</span>
						<span>·</span>
						<span>{m.space}</span>
						<span>·</span>
						<span>{m.updated}</span>
					</div>
				</div>
			</div>
		</Card>
	);
}

export default function Memory() {
	const [params, setParams] = useSearchParams();
	const tier = params.get("tier") as Tier | null;
	const space = params.get("space");
	const source = params.get("source");

	const items = useMemo(() => {
		let list = MEMORIES;
		if (tier) list = list.filter((m) => m.tier === tier);
		if (source) list = list.filter((m) => m.source === source);
		if (space) {
			const name = SPACES.find((s) => s.id === space)?.name;
			list = list.filter((m) => m.space === name);
		}
		return list;
	}, [tier, space, source]);

	const active = tier ?? space ?? source;

	const heading = tier
		? TIER_META[tier].label
		: space
			? (SPACES.find((s) => s.id === space)?.name ?? "Space")
			: source
				? SOURCE_BY_ID[source as keyof typeof SOURCE_BY_ID].name
				: "All memory";

	const description = tier
		? TIER_META[tier].blurb
		: "Everything captured across your sources, ranked by relevance and freshness.";

	return (
		<>
			<PageHeader
				title={heading}
				description={description}
				right={
					<div className="flex items-center gap-2 text-2xs text-ink-3">
						<Filter size={13} />
						{items.length} of {MEMORIES.length}
					</div>
				}
			/>

			{/* tier filter strip */}
			<div className="flex flex-wrap items-center gap-2 border-b border-line px-6 py-3 sm:px-8">
				<button
					type="button"
					onClick={() => setParams({})}
					className={cx(
						"rounded-lg border px-2.5 py-1 text-2xs font-medium transition-colors",
						!active
							? "border-line-strong bg-surface-2 text-ink"
							: "border-line text-ink-2 hover:bg-surface-2 hover:text-ink",
					)}
				>
					All
				</button>
				{TIERS.map((t) => (
					<button
						key={t}
						type="button"
						onClick={() => setParams(tier === t ? {} : { tier: t })}
						className={cx(
							"inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-2xs font-medium transition-colors",
							tier === t
								? "border-line-strong bg-surface-2 text-ink"
								: "border-line text-ink-2 hover:bg-surface-2 hover:text-ink",
						)}
					>
						<span
							className="size-1.5 rounded-full"
							style={{ background: `var(--tier-${t})` }}
						/>
						{TIER_META[t].label}
					</button>
				))}

				{active && (
					<button
						type="button"
						onClick={() => setParams({})}
						className="ml-auto text-2xs text-ink-3 underline-offset-4 hover:text-ink hover:underline"
					>
						Clear filter
					</button>
				)}
			</div>

			<div className="mx-auto max-w-4xl space-y-3 px-6 py-6 sm:px-8">
				{items.length === 0 ? (
					<Card className="flex flex-col items-center gap-2 px-6 py-16 text-center">
						<Info size={20} className="text-ink-3" />
						<p className="text-sm font-medium text-ink">Nothing here yet</p>
						<p className="max-w-sm text-[13px] text-ink-2">
							Memory accumulates as your sources sync. Nothing to write by hand.
						</p>
					</Card>
				) : (
					items.map((m) => <MemoryCard key={m.id} id={m.id} />)
				)}
			</div>
		</>
	);
}
