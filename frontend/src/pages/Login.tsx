import { ArrowRight, Lock, Mail, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ContextGraph, SourceTile, Wordmark } from "../components/brand";
import { Button, Card, Field } from "../components/ui";
import { SOURCES } from "../lib/data";
import { useSession } from "../lib/session";
import { TIER_META, TIERS } from "../lib/types";

export default function Login() {
	const navigate = useNavigate();
	const { session, patch } = useSession();
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [busy, setBusy] = useState(false);

	const submit = (e: FormEvent) => {
		e.preventDefault();
		if (!email.trim() || !password) return;
		setBusy(true);
		// Placeholder for POST /api/auth/login — see lib/session.ts.
		window.setTimeout(() => {
			patch({ email: email.trim() });
			navigate(session.onboarded ? "/memory" : "/onboarding", { replace: true });
		}, 350);
	};

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

						<form onSubmit={submit} className="mt-8 space-y-4">
							<Field
								label="Work email"
								type="email"
								autoComplete="email"
								placeholder="you@company.com"
								icon={<Mail size={15} />}
								value={email}
								onChange={(e) => setEmail(e.target.value)}
								required
							/>
							<Field
								label="Password"
								type="password"
								autoComplete="current-password"
								placeholder="••••••••••••"
								icon={<Lock size={15} />}
								value={password}
								onChange={(e) => setPassword(e.target.value)}
								required
							/>

							<div className="flex items-center justify-between pt-1">
								<label className="flex cursor-pointer items-center gap-2 text-[13px] text-ink-2">
									<input
										type="checkbox"
										defaultChecked
										className="size-3.5 rounded border-line accent-[var(--brand)]"
									/>
									Keep me signed in
								</label>
								<a
									href="#reset"
									className="text-[13px] text-ink-2 underline-offset-4 hover:text-ink hover:underline"
								>
									Forgot password?
								</a>
							</div>

							<Button type="submit" size="lg" full disabled={busy}>
								{busy ? "Signing in…" : "Sign in"}
								{!busy && <ArrowRight size={16} />}
							</Button>
						</form>

						<div className="my-6 flex items-center gap-3 text-2xs text-ink-3">
							<span className="h-px flex-1 bg-line" />
							OR CONTINUE WITH
							<span className="h-px flex-1 bg-line" />
						</div>

						<div className="grid grid-cols-2 gap-3">
							<Button variant="secondary" onClick={() => setEmail("dev@github.com")}>
								<SourceTile id="github" size={18} />
								GitHub
							</Button>
							<Button variant="secondary" onClick={() => setEmail("dev@slack.com")}>
								<SourceTile id="slack" size={18} />
								Slack
							</Button>
						</div>

						<p className="mt-8 text-[13px] text-ink-2">
							No workspace yet?{" "}
							<button
								type="button"
								onClick={() => navigate("/onboarding")}
								className="font-medium text-brand underline-offset-4 hover:underline"
							>
								Create one
							</button>
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
