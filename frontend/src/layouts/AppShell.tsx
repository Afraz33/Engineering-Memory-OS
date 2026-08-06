import { CornerDownLeft, Menu, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Navigate, Outlet, useNavigate } from "react-router-dom";
import { SourceTile } from "../components/brand";
import { TierBadge } from "../components/ui";
import { cx } from "../lib/cx";
import { MEMORIES } from "../lib/data";
import { useSession } from "../lib/session";
import Sidebar from "./Sidebar";

function CommandPalette({ onClose }: { onClose: () => void }) {
	const navigate = useNavigate();
	const [q, setQ] = useState("");

	const results = useMemo(() => {
		const term = q.trim().toLowerCase();
		if (!term) return MEMORIES.slice(0, 6);
		return MEMORIES.filter(
			(m) =>
				m.title.toLowerCase().includes(term) || m.body.toLowerCase().includes(term),
		).slice(0, 8);
	}, [q]);

	useEffect(() => {
		const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
		window.addEventListener("keydown", esc);
		return () => window.removeEventListener("keydown", esc);
	}, [onClose]);

	return (
		<div
			className="fixed inset-0 z-50 flex items-start justify-center bg-black/55 px-4 pt-[12vh] backdrop-blur-sm"
			onClick={onClose}
		>
			<div
				className="w-full max-w-xl overflow-hidden rounded-card border border-line-strong bg-surface shadow-lift"
				onClick={(e) => e.stopPropagation()}
			>
				<div className="flex items-center gap-3 border-b border-line px-4">
					<Search size={16} className="shrink-0 text-ink-3" />
					{/* eslint-disable-next-line jsx-a11y/no-autofocus */}
					<input
						autoFocus
						value={q}
						onChange={(e) => setQ(e.target.value)}
						placeholder="Search memory, decisions, sources…"
						className="h-12 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-3"
					/>
					<kbd className="rounded border border-line px-1.5 py-0.5 font-mono text-2xs text-ink-3">
						ESC
					</kbd>
				</div>

				<div className="max-h-80 overflow-y-auto p-2">
					{results.length === 0 && (
						<p className="px-3 py-8 text-center text-[13px] text-ink-3">
							Nothing matched “{q}”.
						</p>
					)}
					{results.map((m) => (
						<button
							key={m.id}
							type="button"
							onClick={() => {
								navigate(`/memory?focus=${m.id}`);
								onClose();
							}}
							className="flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-surface-2"
						>
							<SourceTile id={m.source} size={26} />
							<span className="min-w-0 flex-1">
								<span className="block truncate text-[13px] font-medium text-ink">
									{m.title}
								</span>
								<span className="mt-0.5 block truncate text-2xs text-ink-3">
									{m.sourceLabel} · {m.space}
								</span>
							</span>
							<TierBadge tier={m.tier} size="sm" />
						</button>
					))}
				</div>

				<div className="flex items-center gap-4 border-t border-line bg-surface-2 px-4 py-2 text-2xs text-ink-3">
					<span className="flex items-center gap-1">
						<CornerDownLeft size={11} /> open
					</span>
					<span>{results.length} results</span>
				</div>
			</div>
		</div>
	);
}

export default function AppShell() {
	const { session } = useSession();
	const [palette, setPalette] = useState(false);
	const [drawer, setDrawer] = useState(false);

	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
				e.preventDefault();
				setPalette((v) => !v);
			}
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, []);

	if (!session.onboarded) return <Navigate to="/onboarding" replace />;

	return (
		<div className="flex h-screen overflow-hidden bg-canvas">
			{/* desktop sidebar */}
			<div className="hidden md:block">
				<Sidebar onSearch={() => setPalette(true)} />
			</div>

			{/* mobile drawer */}
			{drawer && (
				<div className="fixed inset-0 z-40 md:hidden">
					<div
						className="absolute inset-0 bg-black/55"
						onClick={() => setDrawer(false)}
					/>
					<div className="absolute inset-y-0 left-0">
						<Sidebar
							onSearch={() => {
								setDrawer(false);
								setPalette(true);
							}}
						/>
					</div>
				</div>
			)}

			<div className="flex min-w-0 flex-1 flex-col">
				<header
					className={cx(
						"flex h-12 shrink-0 items-center gap-3 border-b border-line px-3 md:hidden",
					)}
				>
					<button
						type="button"
						onClick={() => setDrawer((v) => !v)}
						aria-label="Menu"
						className="rounded p-1.5 text-ink-2 hover:bg-surface-2"
					>
						{drawer ? <X size={18} /> : <Menu size={18} />}
					</button>
					<span className="wordmark text-sm text-ink">Memory OS</span>
					<button
						type="button"
						onClick={() => setPalette(true)}
						aria-label="Search"
						className="ml-auto rounded p-1.5 text-ink-2 hover:bg-surface-2"
					>
						<Search size={17} />
					</button>
				</header>

				<main className="min-w-0 flex-1 overflow-y-auto">
					<Outlet />
				</main>
			</div>

			{palette && <CommandPalette onClose={() => setPalette(false)} />}
		</div>
	);
}
