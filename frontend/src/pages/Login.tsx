import {
	CheckCircle2,
	MessageCircleMore,
	ShieldCheck,
	Zap,
} from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ContextGraph, SourceTile, Wordmark } from "../components/brand";
import { Card } from "../components/ui";
import { SOURCES } from "../lib/data";
import { useSession } from "../lib/session";
import { TIER_META, TIERS } from "../lib/types";

const BENEFITS = [
	{ label: "No credit card required", icon: CheckCircle2 },
	{ label: "Enterprise-grade security", icon: ShieldCheck },
	{ label: "30-second setup", icon: Zap },
];

export default function Login() {
	const navigate = useNavigate();
	const { patch } = useSession();
	const [busy, setBusy] = useState(false);

	const openUiPreview = () => {
		if (busy) return;
		setBusy(true);

		// UI-only session for the MVP. Replace this handler with the agreed
		// Google OAuth exchange once the backend auth contract is available.
		window.setTimeout(() => {
			patch({
				email: "felix.dev@acme.io",
				workspace: "acme-engineering",
				onboarded: true,
				sources: ["github", "slack", "jira"],
			});
			navigate("/dashboard", { replace: true });
		}, 250);
	};

	return (
		<div className="grid min-h-screen bg-canvas lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
			<section className="flex min-h-screen flex-col px-6 py-8 sm:px-12 lg:px-16">
				<Wordmark sub="Shared context for you and your agents" />

				<main className="flex flex-1 items-center justify-center py-12">
					<div className="w-full max-w-sm animate-fade-up">
						<p className="text-2xs font-semibold uppercase tracking-[0.14em] text-brand">
							Engineering Memory OS
						</p>
						<h1 className="display mt-4 text-3xl text-ink sm:text-4xl">
							Welcome to Memory OS.
						</h1>
						<p className="mt-3 text-sm leading-relaxed text-ink-2">
							Capture decisions from Slack, GitHub and Jira, then make them
							queryable for teammates and AI agents.
						</p>

						<Card className="mt-8 p-5 shadow-lift">
							<h2 className="text-lg font-semibold text-ink">Get started</h2>
							<p className="mt-1.5 text-[13px] text-ink-2">
								Sign in with Google to open the workspace preview.
							</p>

							<button
								type="button"
								onClick={openUiPreview}
								disabled={busy}
								className="mt-6 flex h-12 w-full items-center justify-center gap-3 rounded-xl bg-[#171412] px-5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#2b2521] disabled:cursor-wait disabled:opacity-65"
							>
								<span className="flex size-5 items-center justify-center rounded-full bg-white text-[13px] font-bold text-[#171412]">
									G
								</span>
								{busy ? "Opening workspace..." : "Sign in with Google"}
							</button>
						</Card>

						<div className="mt-6 space-y-3">
							{BENEFITS.map(({ label, icon: Icon }) => (
								<div key={label} className="flex items-center gap-3 text-[13px] text-ink-2">
									<Icon size={17} className="text-brand" />
									{label}
								</div>
							))}
						</div>
					</div>
				</main>

				<footer className="text-2xs text-ink-3">
					<p className="flex flex-wrap items-center gap-2">
						Questions?
						<span aria-hidden="true">-</span>
						<a href="#support" className="inline-flex items-center gap-1.5 hover:text-ink">
							<MessageCircleMore size={13} />
							Chat with us
						</a>
					</p>
				</footer>
			</section>

			<aside className="relative hidden overflow-hidden border-l border-line lg:flex lg:flex-col aurora">
				<div className="flex flex-1 flex-col justify-center gap-10 px-14 py-16">
					<div className="max-w-md">
						<h2 className="display text-[28px] text-ink">
							One memory. Every tool.
						</h2>
						<p className="mt-3 text-sm leading-relaxed text-ink-2">
							Stop hand-maintaining a log nobody updates. Memory OS reads the work
							you already do: pull requests, threads, tickets and agent sessions.
						</p>
					</div>

					<ContextGraph className="w-full max-w-lg" />

					<div className="grid max-w-md grid-cols-2 gap-3">
						{TIERS.map((tier) => (
							<Card key={tier} className="p-3.5">
								<div className={`text-[13px] font-semibold ${TIER_META[tier].className}`}>
									{TIER_META[tier].label}
								</div>
								<p className="mt-1 text-2xs leading-relaxed text-ink-3">
									{TIER_META[tier].blurb}
								</p>
							</Card>
						))}
					</div>

					<div className="flex flex-wrap items-center gap-x-5 gap-y-3">
						<div className="flex gap-1.5">
							{SOURCES.slice(0, 6).map((source) => (
								<div key={source.id}>
									<SourceTile id={source.id} size={30} />
								</div>
							))}
						</div>
						<span className="rounded-full border border-line bg-surface/70 px-3 py-1.5 text-2xs font-medium text-ink-2">
							{SOURCES.filter((source) => source.available).length} sources supported
						</span>
					</div>
				</div>
			</aside>
		</div>
	);
}
