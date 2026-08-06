import { CornerDownLeft, Sparkles } from "lucide-react";
import { type FormEvent, useState } from "react";
import { SourceTile } from "../components/brand";
import { Button, Card, TierBadge } from "../components/ui";
import { MEMORIES } from "../lib/data";

const SUGGESTIONS = [
	"Why did we move off MongoDB?",
	"What are the constraints on the ADNOC deployment?",
	"What's in scope for Memory OS right now?",
];

export default function Ask() {
	const [q, setQ] = useState("");
	const [asked, setAsked] = useState<string | null>(null);

	const cited = MEMORIES.filter((m) => !m.supersededBy).slice(0, 3);

	const submit = (e: FormEvent) => {
		e.preventDefault();
		if (q.trim()) setAsked(q.trim());
	};

	return (
		<div className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-10 sm:px-8">
			<div className="flex items-center gap-2 text-brand">
				<Sparkles size={16} />
				<span className="text-2xs font-semibold uppercase tracking-[0.14em]">
					Ask memory
				</span>
			</div>

			<h1 className="display mt-3 text-2xl text-ink">
				Query the same context your agents read
			</h1>
			<p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-2">
				Answers cite the thread, review or session they came from, and never
				return a decision that was later reversed.
			</p>

			<form onSubmit={submit} className="mt-7">
				<div className="flex items-center gap-2 rounded-card border border-line bg-surface-2 px-3 focus-within:border-brand">
					<input
						value={q}
						onChange={(e) => setQ(e.target.value)}
						placeholder="Ask anything about your projects, decisions or preferences…"
						className="h-12 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-3"
					/>
					<Button type="submit" size="sm" disabled={!q.trim()}>
						<CornerDownLeft size={13} />
						Ask
					</Button>
				</div>
			</form>

			{!asked && (
				<div className="mt-4 flex flex-wrap gap-2">
					{SUGGESTIONS.map((s) => (
						<button
							key={s}
							type="button"
							onClick={() => {
								setQ(s);
								setAsked(s);
							}}
							className="rounded-lg border border-line px-3 py-1.5 text-2xs text-ink-2 transition-colors hover:border-line-strong hover:bg-surface-2 hover:text-ink"
						>
							{s}
						</button>
					))}
				</div>
			)}

			{asked && (
				<div className="mt-7 space-y-3 animate-fade-up">
					<p className="text-2xs uppercase tracking-[0.12em] text-ink-3">
						Retrieved context
					</p>
					{cited.map((m) => (
						<Card key={m.id} className="flex items-start gap-3 p-4">
							<SourceTile id={m.source} size={30} />
							<div className="min-w-0 flex-1">
								<div className="flex items-center gap-2">
									<TierBadge tier={m.tier} size="sm" />
									<span className="truncate text-2xs text-ink-3">
										{m.sourceLabel}
									</span>
								</div>
								<h3 className="mt-1.5 text-[13px] font-medium text-ink">
									{m.title}
								</h3>
								<p className="mt-1 text-2xs leading-relaxed text-ink-2">{m.body}</p>
							</div>
						</Card>
					))}
					<p className="pt-2 text-2xs text-ink-3">
						Generation is wired to the backend once the retrieval API lands — these
						are the passages that would be sent as context.
					</p>
				</div>
			)}
		</div>
	);
}
