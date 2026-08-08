import {
	ArrowLeft,
	ArrowRight,
	Check,
	Cloud,
	Copy,
	HardDrive,
	Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SourceTile, Wordmark } from "../components/brand";
import { Button, Card, Field, SectionTitle } from "../components/ui";
import { cx } from "../lib/cx";
import { KIND_LABEL, SOURCES } from "../lib/data";
import { useSession } from "../lib/session";
import { TIER_META, TIERS, type SourceId, type Tier } from "../lib/types";

const STEPS = [
	{ key: "workspace", label: "Workspace", blurb: "Name your context" },
	{ key: "sources", label: "Sources", blurb: "Where memory comes from" },
	{ key: "tiers", label: "Memory", blurb: "What's worth keeping" },
	{ key: "deployment", label: "Deployment", blurb: "Where it runs" },
	{ key: "connect", label: "Connect", blurb: "Point your agents at it" },
] as const;

const MCP_SNIPPET = `{
  "mcpServers": {
    "memory-os": {
      "command": "memory-os",
      "args": ["serve", "--stdio"],
      "env": { "MEMORY_OS_WORKSPACE": "WORKSPACE_SLUG" }
    }
  }
}`;

export default function Onboarding() {
	const navigate = useNavigate();
	const { session, patch } = useSession();

	const [step, setStep] = useState(0);
	const [workspace, setWorkspace] = useState(session.workspace);
	const [sources, setSources] = useState<SourceId[]>(session.sources);
	const [tiers, setTiers] = useState<Tier[]>(session.tiers);
	const [deployment, setDeployment] = useState(session.deployment);
	const [copied, setCopied] = useState(false);

	const slug = useMemo(
		() =>
			workspace.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") ||
			"my-workspace",
		[workspace],
	);

	const canAdvance =
		(step === 0 && workspace.trim().length > 1) ||
		(step === 1 && sources.length > 0) ||
		(step === 2 && tiers.length > 0) ||
		step === 3 ||
		step === 4;

	const next = () => {
		if (step < STEPS.length - 1) {
			setStep(step + 1);
			return;
		}
		patch({
			workspace: workspace.trim(),
			sources,
			tiers,
			deployment,
			onboarded: true,
		});
		navigate("/dashboard", { replace: true });
	};

	const toggleSource = (id: SourceId) =>
		setSources((prev) =>
			prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
		);

	const toggleTier = (t: Tier) =>
		setTiers((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));

	const copySnippet = () => {
		navigator.clipboard?.writeText(MCP_SNIPPET.replace("WORKSPACE_SLUG", slug));
		setCopied(true);
		window.setTimeout(() => setCopied(false), 1600);
	};

	return (
		<div className="grid min-h-screen lg:grid-cols-[300px_minmax(0,1fr)]">
			{/* ── progress rail ────────────────────────────────────── */}
			<aside className="hidden flex-col border-r border-line bg-surface px-7 py-8 lg:flex">
				<Wordmark sub="Setup" />

				<ol className="mt-12 space-y-1">
					{STEPS.map((s, i) => {
						const done = i < step;
						const active = i === step;
						return (
							<li key={s.key}>
								<button
									type="button"
									disabled={i > step}
									onClick={() => setStep(i)}
									className={cx(
										"flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors",
										active && "bg-surface-2",
										i > step ? "cursor-default opacity-45" : "hover:bg-surface-2",
									)}
								>
									<span
										className={cx(
											"mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border text-2xs font-semibold",
											done && "border-brand bg-brand text-brand-ink",
											active && !done && "border-brand text-brand",
											!done && !active && "border-line text-ink-3",
										)}
									>
										{done ? <Check size={11} strokeWidth={3} /> : i + 1}
									</span>
									<span className="min-w-0">
										<span
											className={cx(
												"block text-[13px] font-medium",
												active ? "text-ink" : "text-ink-2",
											)}
										>
											{s.label}
										</span>
										<span className="block text-2xs text-ink-3">{s.blurb}</span>
									</span>
								</button>
							</li>
						);
					})}
				</ol>

				<div className="mt-auto rounded-card border border-line bg-surface-2 p-4">
					<p className="text-2xs leading-relaxed text-ink-2">
						Everything here is changeable later. Nothing is captured until you
						confirm on the last step.
					</p>
				</div>
			</aside>

			{/* ── step body ────────────────────────────────────────── */}
			<main className="flex flex-col">
				<div className="flex flex-1 justify-center px-6 py-10 sm:px-10 lg:px-16 lg:py-16">
					<div key={step} className="w-full max-w-2xl animate-fade-up">
						<p className="text-2xs font-medium uppercase tracking-[0.14em] text-ink-3">
							Step {step + 1} of {STEPS.length}
						</p>

						{step === 0 && (
							<div className="mt-4 space-y-7">
								<div>
									<h1 className="display text-3xl text-ink">
										Name your workspace
									</h1>
									<p className="mt-2 text-sm leading-relaxed text-ink-2">
										A workspace is one shared context — a team, a company, or just
										you. Agents address it by slug.
									</p>
								</div>
								<div className="max-w-md space-y-4">
									<Field
										label="Workspace name"
										placeholder="Acme Engineering"
										value={workspace}
										onChange={(e) => setWorkspace(e.target.value)}
										autoFocus
									/>
									<div className="rounded-lg border border-line bg-surface-2 px-3 py-2.5">
										<span className="text-2xs text-ink-3">Agents will connect to</span>
										<div className="mt-0.5 font-mono text-[13px] text-ink">
											memory-os://{slug}
										</div>
									</div>
								</div>
							</div>
						)}

						{step === 1 && (
							<div className="mt-4 space-y-7">
								<div>
									<h1 className="display text-3xl text-ink">
										Where should memory come from?
									</h1>
									<p className="mt-2 text-sm leading-relaxed text-ink-2">
										Pick the tools you already work in. Memory OS reads them —
										you never write a log entry by hand.
									</p>
								</div>

								<div className="grid gap-3 sm:grid-cols-2">
									{SOURCES.map((s) => {
										const on = sources.includes(s.id);
										return (
											<button
												key={s.id}
												type="button"
												disabled={!s.available}
												onClick={() => toggleSource(s.id)}
												className={cx(
													"group flex items-start gap-3 rounded-card border p-4 text-left transition-all duration-150",
													on
														? "border-brand bg-brand-soft"
														: "border-line bg-surface hover:border-line-strong hover:bg-surface-2",
													!s.available && "cursor-not-allowed opacity-45",
												)}
											>
												<SourceTile id={s.id} size={36} muted={!s.available} />
												<span className="min-w-0 flex-1">
													<span className="flex items-center gap-2">
														<span className="text-sm font-medium text-ink">
															{s.name}
														</span>
														<span className="rounded border border-line px-1.5 py-px text-2xs text-ink-3">
															{KIND_LABEL[s.kind]}
														</span>
													</span>
													<span className="mt-1 block text-2xs leading-relaxed text-ink-3">
														{s.available ? s.captures : "Coming soon"}
													</span>
												</span>
												<span
													className={cx(
														"mt-0.5 flex size-4.5 shrink-0 items-center justify-center rounded-md border transition-colors",
														on
															? "border-brand bg-brand text-brand-ink"
															: "border-line-strong",
													)}
												>
													{on && <Check size={11} strokeWidth={3} />}
												</span>
											</button>
										);
									})}
								</div>
							</div>
						)}

						{step === 2 && (
							<div className="mt-4 space-y-7">
								<div>
									<h1 className="display text-3xl text-ink">
										What's worth remembering?
									</h1>
									<p className="mt-2 text-sm leading-relaxed text-ink-2">
										Not every message is memory. Each captured item is sorted into
										one tier, and retrieval weights them differently.
									</p>
								</div>

								<div className="space-y-3">
									{TIERS.map((t) => {
										const on = tiers.includes(t);
										const meta = TIER_META[t];
										return (
											<button
												key={t}
												type="button"
												onClick={() => toggleTier(t)}
												className={cx(
													"flex w-full items-start gap-4 rounded-card border p-4 text-left transition-all duration-150",
													on
														? "border-line-strong bg-surface-2"
														: "border-line bg-surface hover:bg-surface-2",
												)}
											>
												<span
													className={cx(
														"mt-1 h-10 w-1 shrink-0 rounded-full",
														on ? "opacity-100" : "opacity-30",
													)}
													style={{ background: `var(--tier-${t})` }}
												/>
												<span className="min-w-0 flex-1">
													<span className="flex flex-wrap items-center gap-2">
														<span className={cx("text-sm font-semibold", meta.className)}>
															{meta.label}
														</span>
														<span className="rounded border border-line px-1.5 py-px text-2xs text-ink-3">
															{meta.retention}
														</span>
													</span>
													<span className="mt-1 block text-[13px] leading-relaxed text-ink-2">
														{meta.blurb}
													</span>
												</span>
												<span
													className={cx(
														"mt-0.5 flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors",
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
							</div>
						)}

						{step === 3 && (
							<div className="mt-4 space-y-7">
								<div>
									<h1 className="display text-3xl text-ink">Where does it run?</h1>
									<p className="mt-2 text-sm leading-relaxed text-ink-2">
										The index, the embeddings and the model key are all yours.
										This choice decides where they live.
									</p>
								</div>

								<div className="grid gap-3 sm:grid-cols-2">
									{(
										[
											{
												id: "local" as const,
												icon: HardDrive,
												title: "Local",
												tag: "Recommended",
												points: [
													"SQLite index on your machine",
													"Embeddings run on-device",
													"Bring your own model key",
													"Works fully offline",
												],
											},
											{
												id: "cloud" as const,
												icon: Cloud,
												title: "Hosted",
												tag: "Managed",
												points: [
													"We run the index for you",
													"Shared across the team by default",
													"Automatic backups",
													"Requires network egress",
												],
											},
										]
									).map((opt) => {
										const on = deployment === opt.id;
										const Icon = opt.icon;
										return (
											<button
												key={opt.id}
												type="button"
												onClick={() => setDeployment(opt.id)}
												className={cx(
													"rounded-card border p-5 text-left transition-all duration-150",
													on
														? "border-brand bg-brand-soft"
														: "border-line bg-surface hover:border-line-strong hover:bg-surface-2",
												)}
											>
												<div className="flex items-center justify-between">
													<Icon size={20} className={on ? "text-brand" : "text-ink-2"} />
													<span className="rounded border border-line px-1.5 py-px text-2xs text-ink-3">
														{opt.tag}
													</span>
												</div>
												<div className="mt-3 text-sm font-semibold text-ink">
													{opt.title}
												</div>
												<ul className="mt-3 space-y-1.5">
													{opt.points.map((p) => (
														<li
															key={p}
															className="flex items-start gap-2 text-2xs leading-relaxed text-ink-2"
														>
															<Check
																size={12}
																className="mt-0.5 shrink-0 text-ink-3"
															/>
															{p}
														</li>
													))}
												</ul>
											</button>
										);
									})}
								</div>
							</div>
						)}

						{step === 4 && (
							<div className="mt-4 space-y-7">
								<div>
									<h1 className="display text-3xl text-ink">
										Point your agents at it
									</h1>
									<p className="mt-2 text-sm leading-relaxed text-ink-2">
										Memory OS speaks MCP. Drop this into Claude Code, Codex, Cursor
										or any MCP client and they all read the same context.
									</p>
								</div>

								<Card className="overflow-hidden">
									<div className="flex items-center justify-between border-b border-line bg-surface-2 px-4 py-2.5">
										<span className="font-mono text-2xs text-ink-3">
											~/.config/mcp/servers.json
										</span>
										<Button size="sm" variant="ghost" onClick={copySnippet}>
											{copied ? <Check size={13} /> : <Copy size={13} />}
											{copied ? "Copied" : "Copy"}
										</Button>
									</div>
									<pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-ink-2">
										{MCP_SNIPPET.replace("WORKSPACE_SLUG", slug)}
									</pre>
								</Card>

								<Card className="p-5">
									<SectionTitle
										title="What happens next"
										description="Nothing has been read yet. Capture begins when you finish setup."
									/>
									<ul className="mt-4 space-y-2.5">
										{[
											`Start capturing new activity from ${sources.length} connected source${sources.length === 1 ? "" : "s"}`,
											"Extract decisions and classify each into a tier",
											"Link supersessions so reversed calls never resurface",
											"Expose everything over MCP and the search API",
										].map((line, i) => (
											<li key={line} className="flex items-start gap-3 text-[13px] text-ink-2">
												<span className="mt-px flex size-4.5 shrink-0 items-center justify-center rounded-full border border-line text-2xs text-ink-3">
													{i + 1}
												</span>
												{line}
											</li>
										))}
									</ul>
								</Card>
							</div>
						)}
					</div>
				</div>

				{/* ── footer nav ───────────────────────────────────── */}
				<div className="sticky bottom-0 border-t border-line bg-canvas/85 px-6 py-4 backdrop-blur sm:px-10 lg:px-16">
					<div className="mx-auto flex max-w-2xl items-center justify-between gap-4">
						<Button
							variant="ghost"
							onClick={() => (step === 0 ? navigate("/login") : setStep(step - 1))}
						>
							<ArrowLeft size={16} />
							{step === 0 ? "Back to sign in" : "Back"}
						</Button>

						<div className="flex items-center gap-3">
							{step === 1 && (
								<span className="text-2xs text-ink-3">
									{sources.length} selected
								</span>
							)}
							<Button size="lg" onClick={next} disabled={!canAdvance}>
								{step === STEPS.length - 1 ? (
									<>
										<Sparkles size={16} />
										Start capturing
									</>
								) : (
									<>
										Continue
										<ArrowRight size={16} />
									</>
								)}
							</Button>
						</div>
					</div>
				</div>
			</main>
		</div>
	);
}
