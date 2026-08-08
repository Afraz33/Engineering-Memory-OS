import {
	ChevronDown,
	CircleHelp,
	LayoutDashboard,
	LogOut,
	Moon,
	PlugZap,
	Settings,
	Sun,
	Users,
} from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { Wordmark } from "../components/brand";
import { cx } from "../lib/cx";
import { useSession, useTheme } from "../lib/session";

const NAV_ITEMS = [
	{ to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
	{ to: "/connections", label: "Connections", icon: PlugZap },
	{ to: "/team", label: "Team", icon: Users },
	{ to: "/settings", label: "Settings", icon: Settings },
];

const profileFromEmail = (email: string | null) => {
	const value = email || "felix.dev@acme.io";
	const parts = value.split("@")[0].split(/[._-]/).filter(Boolean);
	const name = parts.map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
	const initials = parts.slice(0, 2).map((part) => part.charAt(0).toUpperCase()).join("");
	return { email: value, name: name || "Felix Dev", initials: initials || "FD" };
};

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
	const navigate = useNavigate();
	const { session, signOut } = useSession();
	const { theme, toggle } = useTheme();
	const profile = profileFromEmail(session.email);
	const workspace = session.workspace || "acme-engineering";

	return (
		<nav className="flex h-full w-[264px] shrink-0 flex-col border-r border-line bg-surface">
			<div className="border-b border-line px-5 py-5">
				<Wordmark />
			</div>

			<div className="border-b border-line px-4 py-4">
				<div className="px-1 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-3">
					Workspace
				</div>
				<button
					type="button"
					className="mt-2 flex w-full items-center gap-3 rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-left transition-colors hover:border-line-strong hover:bg-surface-3"
				>
					<span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-brand text-sm font-semibold text-brand-ink">
						{workspace.charAt(0).toUpperCase()}
					</span>
					<span className="min-w-0 flex-1">
						<span className="block truncate text-[13px] font-semibold text-ink">{workspace}</span>
						<span className="block text-2xs text-ink-3">2 members</span>
					</span>
					<ChevronDown size={14} className="text-ink-3" />
				</button>
			</div>

			<div className="flex-1 space-y-1 px-3 py-5">
				{NAV_ITEMS.map(({ to, label, icon: Icon }) => (
					<NavLink
						key={to}
						to={to}
						onClick={onNavigate}
						className={({ isActive }) =>
							cx(
								"flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-colors",
								isActive
									? "bg-brand text-brand-ink shadow-sm"
									: "text-ink-2 hover:bg-surface-2 hover:text-ink",
							)
						}
					>
						<Icon size={17} />
						{label}
					</NavLink>
				))}
			</div>

			<div className="border-t border-line p-3">
				<div className="flex items-center gap-3 rounded-xl px-2 py-2">
					<span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-soft text-2xs font-semibold text-brand">
						{profile.initials}
					</span>
					<span className="min-w-0 flex-1">
						<span className="block truncate text-[13px] font-semibold text-ink">{profile.name}</span>
						<span className="block truncate text-2xs text-ink-3">{profile.email}</span>
					</span>
					<button
						type="button"
						onClick={toggle}
						aria-label="Toggle theme"
						className="rounded-lg p-1.5 text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink"
					>
						{theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
					</button>
				</div>

				<div className="mt-1 grid grid-cols-2 gap-1">
					<button type="button" className="flex items-center justify-center gap-2 rounded-lg px-2 py-2 text-2xs text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink">
						<CircleHelp size={14} />
						Help
					</button>
					<button
						type="button"
						onClick={() => {
							signOut();
							navigate("/login", { replace: true });
							onNavigate?.();
						}}
						className="flex items-center justify-center gap-2 rounded-lg px-2 py-2 text-2xs text-ink-3 transition-colors hover:bg-surface-2 hover:text-danger"
					>
						<LogOut size={14} />
						Sign out
					</button>
				</div>
			</div>
		</nav>
	);
}
