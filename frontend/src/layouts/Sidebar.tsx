import {
	ChevronDown,
	ChevronsUpDown,
	GitBranch,
	Layers3,
	LogOut,
	Moon,
	Plus,
	Search,
	Settings,
	Sparkles,
	Sun,
} from "lucide-react";
import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Mark, SourceTile } from "../components/brand";
import { StatusDot } from "../components/ui";
import { cx } from "../lib/cx";
import { CONNECTIONS, MEMORIES, SOURCE_BY_ID, SPACES } from "../lib/data";
import { useAuth } from "../lib/auth-context";
import { useSession, useTheme } from "../lib/session";
import { TIERS, TIER_META } from "../lib/types";

/**
 * Sidebar structure follows Slite's information hierarchy — workspace
 * switcher, then search, then an AI entry point, then collapsible
 * collections — but the collections here are memory tiers, spaces and
 * sources rather than document folders.
 */

function SectionHeader({
	label,
	open,
	onToggle,
	onAdd,
}: {
	label: string;
	open: boolean;
	onToggle: () => void;
	onAdd?: () => void;
}) {
	return (
		<div className="group/section flex items-center gap-1 px-2 pb-1 pt-4">
			<button
				type="button"
				onClick={onToggle}
				className="flex flex-1 items-center gap-1 rounded text-2xs font-semibold uppercase tracking-[0.12em] text-ink-3 transition-colors hover:text-ink-2"
			>
				<ChevronDown
					size={11}
					className={cx("transition-transform duration-150", !open && "-rotate-90")}
				/>
				{label}
			</button>
			{onAdd && (
				<button
					type="button"
					onClick={onAdd}
					aria-label={`Add ${label.toLowerCase()}`}
					className="rounded p-0.5 text-ink-3 opacity-0 transition-opacity hover:bg-surface-3 hover:text-ink group-hover/section:opacity-100"
				>
					<Plus size={13} />
				</button>
			)}
		</div>
	);
}

function Row({
	to,
	icon,
	label,
	count,
	trailing,
}: {
	to: string;
	icon: React.ReactNode;
	label: string;
	count?: number;
	trailing?: React.ReactNode;
}) {
	return (
		<NavLink
			to={to}
			className={({ isActive }) =>
				cx(
					"group relative flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13px] transition-colors duration-100",
					isActive
						? "bg-surface-3 font-medium text-ink"
						: "text-ink-2 hover:bg-surface-2 hover:text-ink",
				)
			}
		>
			{({ isActive }) => (
				<>
					{isActive && (
						<span className="absolute -left-2 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-brand" />
					)}
					<span className="flex size-4 shrink-0 items-center justify-center text-ink-3 group-hover:text-ink-2">
						{icon}
					</span>
					<span className="min-w-0 flex-1 truncate">{label}</span>
					{trailing}
					{count !== undefined && (
						<span className="shrink-0 font-mono text-2xs text-ink-3">{count}</span>
					)}
				</>
			)}
		</NavLink>
	);
}

export default function Sidebar({ onSearch }: { onSearch: () => void }) {
	const navigate = useNavigate();
	const { session, signOut } = useSession();
	const { signOut: signOutServer } = useAuth();
	const { theme, toggle } = useTheme();

	const [open, setOpen] = useState({ tiers: true, spaces: true, sources: true });
	const flip = (k: keyof typeof open) => setOpen((s) => ({ ...s, [k]: !s[k] }));

	const tierCount = (t: string) => MEMORIES.filter((m) => m.tier === t).length;

	return (
		<nav className="flex h-full w-[264px] shrink-0 flex-col border-r border-line bg-surface">
			{/* workspace switcher */}
			<button
				type="button"
				className="m-2 flex items-center gap-2.5 rounded-lg px-2 py-2 text-left transition-colors hover:bg-surface-2"
			>
				<Mark size={26} />
				<span className="min-w-0 flex-1">
					<span className="block truncate text-[13px] font-semibold text-ink">
						{session.workspace || "My Workspace"}
					</span>
					<span className="block text-2xs text-ink-3">
						{session.deployment === "local" ? "Local · offline ready" : "Hosted"}
					</span>
				</span>
				<ChevronsUpDown size={13} className="shrink-0 text-ink-3" />
			</button>

			<div className="space-y-1 px-2">
				<button
					type="button"
					onClick={onSearch}
					className="flex w-full items-center gap-2.5 rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 text-[13px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink-2"
				>
					<Search size={14} />
					<span className="flex-1 text-left">Search</span>
					<kbd className="rounded border border-line px-1 font-mono text-2xs">⌘K</kbd>
				</button>

				<NavLink
					to="/ask"
					className={({ isActive }) =>
						cx(
							"flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors",
							isActive
								? "bg-brand-soft text-brand"
								: "text-ink-2 hover:bg-brand-soft hover:text-brand",
						)
					}
				>
					<Sparkles size={14} />
					Ask memory
				</NavLink>
			</div>

			<div className="mt-1 flex-1 overflow-y-auto px-2 pb-2">
				<div className="space-y-0.5 pt-2">
					<Row to="/memory" icon={<Layers3 size={14} />} label="All memory" count={MEMORIES.length} />
					<Row
						to="/timeline"
						icon={<GitBranch size={14} />}
						label="Decision timeline"
						count={MEMORIES.filter((m) => m.tier === "decision").length}
					/>
				</div>

				<SectionHeader label="Tiers" open={open.tiers} onToggle={() => flip("tiers")} />
				{open.tiers && (
					<div className="space-y-0.5">
						{TIERS.map((t) => (
							<Row
								key={t}
								to={`/memory?tier=${t}`}
								icon={
									<span
										className="size-2 rounded-full"
										style={{ background: `var(--tier-${t})` }}
									/>
								}
								label={TIER_META[t].label}
								count={tierCount(t)}
							/>
						))}
					</div>
				)}

				<SectionHeader
					label="Spaces"
					open={open.spaces}
					onToggle={() => flip("spaces")}
					onAdd={() => undefined}
				/>
				{open.spaces && (
					<div className="space-y-0.5">
						{SPACES.map((s) => (
							<Row
								key={s.id}
								to={`/memory?space=${s.id}`}
								icon={
									<span
										className="size-2 rounded-[3px]"
										style={{ background: s.color }}
									/>
								}
								label={s.name}
								count={s.count}
							/>
						))}
					</div>
				)}

				<SectionHeader
					label="Sources"
					open={open.sources}
					onToggle={() => flip("sources")}
					onAdd={() => navigate("/sources")}
				/>
				{open.sources && (
					<div className="space-y-0.5">
						{CONNECTIONS.map((c) => (
							<Row
								key={c.id}
								to={`/memory?source=${c.id}`}
								icon={<SourceTile id={c.id} size={16} />}
								label={SOURCE_BY_ID[c.id].name}
								trailing={<StatusDot status={c.status} />}
							/>
						))}
						<button
							type="button"
							onClick={() => navigate("/sources")}
							className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13px] text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink-2"
						>
							<span className="flex size-4 items-center justify-center">
								<Plus size={13} />
							</span>
							Connect source
						</button>
					</div>
				)}
			</div>

			{/* footer */}
			<div className="border-t border-line p-2">
				<div className="flex items-center gap-2 rounded-lg px-2 py-1.5">
					<span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-3 text-2xs font-semibold text-ink-2">
						{(session.email ?? "you").slice(0, 2).toUpperCase()}
					</span>
					<span className="min-w-0 flex-1 truncate text-[13px] text-ink-2">
						{session.email ?? "you@local"}
					</span>
					<button
						type="button"
						onClick={toggle}
						aria-label="Toggle theme"
						className="rounded p-1 text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink"
					>
						{theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
					</button>
					<NavLink
						to="/settings"
						aria-label="Settings"
						className="rounded p-1 text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink"
					>
						<Settings size={14} />
					</NavLink>
					<button
						type="button"
						onClick={async () => {
							// Clear the cookie server-side too, or the next reload
							// signs straight back in.
							await signOutServer();
							signOut();
							navigate("/login", { replace: true });
						}}
						aria-label="Sign out"
						className="rounded p-1 text-ink-3 transition-colors hover:bg-surface-2 hover:text-danger"
					>
						<LogOut size={14} />
					</button>
				</div>
			</div>
		</nav>
	);
}
