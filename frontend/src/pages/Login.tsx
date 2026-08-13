import { ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ContextGraph, SourceTile, Wordmark } from "../components/brand";
import { Card } from "../components/ui";
import { useAuth } from "../lib/auth-context";
import { SOURCES } from "../lib/data";
import { useSession } from "../lib/session";
import { TIER_META, TIERS } from "../lib/types";

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

export default function Login() {
	const navigate = useNavigate();
	const { signIn } = useAuth();
	const { patch } = useSession();
	const buttonRef = useRef<HTMLDivElement>(null);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (!CLIENT_ID) {
			setError("VITE_GOOGLE_CLIENT_ID is not set — see backend/.env.example.");
			return;
		}

		// The GSI script is `async defer`, so it may not have executed yet when
		// this effect runs. Poll until it lands, then stop.
		const timer = window.setInterval(() => {
			const gsi = window.google?.accounts.id;
			if (!gsi || !buttonRef.current) return;
			window.clearInterval(timer);

			gsi.initialize({
				client_id: CLIENT_ID,
				callback: async ({ credential }) => {
					try {
						const user = await signIn(credential);
						// Mirrored into localStorage only because Sidebar and
						// Settings still read `session.email` for display.
						patch({ email: user.email });
						// Let the top-level router decide: it knows (once the
						// workspace fetch lands) whether this account has one yet.
						navigate("/", { replace: true });
					} catch {
						setError("Sign-in failed. Please try again.");
					}
				},
			});

			gsi.renderButton(buttonRef.current, {
				theme: "outline",
				size: "large",
				text: "continue_with",
				shape: "rectangular",
				width: 320,
			});
		}, 100);

		return () => window.clearInterval(timer);
	}, [navigate, patch, signIn]);

	return (
		<div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
			{/* ── form ─────────────────────────────────────────────── */}
			<div className="flex flex-col px-6 py-8 sm:px-12 lg:px-16">
				<Wordmark sub="Shared context for you and your agents" />

				<div className="flex flex-1 items-center justify-center py-12">
					<div className="w-full max-w-sm animate-fade-up">
						<h1 className="display text-3xl text-ink">Welcome back</h1>
						<p className="mt-2 text-sm leading-relaxed text-ink-2">
							Sign in to the memory layer your tools read from.
						</p>

						{/* Google renders its own button here — their branding
						    guidelines require it, so it does not use <Button>. */}
						<div ref={buttonRef} className="mt-8 min-h-[44px]" />

						{error && (
							<p className="mt-3 text-[13px] text-danger">{error}</p>
						)}

						<p className="mt-6 text-[13px] leading-relaxed text-ink-3">
							First time here? Signing in creates your account — there is
							nothing separate to fill in.
						</p>
					</div>
				</div>

				<p className="flex items-center gap-2 text-2xs text-ink-3">
					<ShieldCheck size={13} />
					Runs local-first — your index, embeddings and keys stay on your infrastructure.
				</p>
			</div>

			{/* ── aside ────────────────────────────────────────────── */}
			<aside className="relative hidden overflow-hidden border-l border-line lg:flex lg:flex-col aurora">
				<div className="flex flex-1 flex-col justify-center gap-10 px-14 py-16">
					<div className="max-w-md">
						<h2 className="display text-[28px] text-ink">
							One memory. Every tool.
						</h2>
						<p className="mt-3 text-sm leading-relaxed text-ink-2">
							Stop hand-maintaining a log nobody updates. Memory OS reads the work
							you already do — pull requests, threads, tickets, agent sessions —
							and turns it into context your tools can query and write back to.
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

					<div className="flex items-center gap-3">
						<div className="flex -space-x-2">
							{SOURCES.slice(0, 6).map((s) => (
								<div key={s.id} className="rounded-lg ring-2 ring-[var(--surface)]">
									<SourceTile id={s.id} size={30} />
								</div>
							))}
						</div>
						<span className="text-2xs text-ink-3">
							{SOURCES.filter((s) => s.available).length} sources supported
						</span>
					</div>
				</div>
			</aside>
		</div>
	);
}
