import {
	Activity,
	BookOpen,
	CheckCircle2,
	Copy,
	DatabaseZap,
	FileStack,
	MessageSquareText,
	Pencil,
	PlugZap,
	Search,
	TicketCheck,
	UserPlus,
	Users,
} from "lucide-react";
import type { ComponentType } from "react";
import { SourceTile } from "../components/brand";
import { Button, Card } from "../components/ui";
import { SOURCE_BY_ID } from "../lib/data";
import { useSession } from "../lib/session";
import type { SourceId } from "../lib/types";

type Icon = ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;

const STATS: Array<{ label: string; value: string; icon: Icon }> = [
	{ label: "Total members", value: "2", icon: Users },
	{ label: "Connected tools", value: "3", icon: PlugZap },
	{ label: "Indexed documents", value: "1.2K", icon: FileStack },
	{ label: "Search queries", value: "42", icon: Search },
];

const INTEGRATIONS: Array<{
	id: Extract<SourceId, "github" | "slack" | "jira">;
	description: string;
}> = [
	{ id: "github", description: "Repositories, pull requests and discussions" },
	{ id: "slack", description: "Channels, threads and team decisions" },
	{ id: "jira", description: "Issues, sprint updates and ticket context" },
];

const RECENT_EVENTS: Array<{
	id: string;
	source: Extract<SourceId, "github" | "slack" | "jira">;
	text: string;
	time: string;
}> = [
	{
		id: "event-1",
		source: "github",
		text: "Indexed 45 commits from the main branch",
		time: "2 min ago",
	},
	{
		id: "event-2",
		source: "slack",
		text: "New thread: Authentication architecture decision",
		time: "15 min ago",
	},
	{
		id: "event-3",
		source: "jira",
		text: "Sprint planning: Q1 roadmap discussion",
		time: "1 hr ago",
	},
	{
		id: "event-4",
		source: "github",
		text: "PR merged: Authentication refactor",
		time: "3 hrs ago",
	},
	{
		id: "event-5",
		source: "slack",
		text: "Synced 12 new knowledge threads",
		time: "5 hrs ago",
	},
];

const ACTIVITIES: Array<{
	id: string;
	icon: Icon;
	lead: string;
	detail: string;
	time: string;
}> = [
	{
		id: "activity-1",
		icon: Copy,
		lead: "Sarah Chen",
		detail: "connected the GitHub repository",
		time: "2 hours ago",
	},
	{
		id: "activity-2",
		icon: MessageSquareText,
		lead: "Alex Rodriguez",
		detail: "indexed 340 Slack messages",
		time: "4 hours ago",
	},
	{
		id: "activity-3",
		icon: TicketCheck,
		lead: "You",
		detail: "connected the Jira workspace",
		time: "1 day ago",
	},
];

const prettyFirstName = (email: string | null) => {
	const raw = email?.split("@")[0]?.split(/[._-]/)[0] || "Felix";
	return raw.charAt(0).toUpperCase() + raw.slice(1);
};

export default function Dashboard() {
	const { session } = useSession();
	const firstName = prettyFirstName(session.email);
	const workspace = session.workspace || "acme-engineering";

	return (
		<>
			<header className="flex flex-wrap items-center gap-4 border-b border-line bg-canvas px-6 py-5 sm:px-8">
				<div className="min-w-0 flex-1">
					<h1 className="display text-2xl text-ink">Dashboard</h1>
					<p className="mt-1 text-[13px] text-ink-2">
						Welcome back, {firstName}. Here&apos;s your workspace overview.
					</p>
				</div>
				<Button>
					<UserPlus size={16} />
					Invite team
				</Button>
			</header>

			<div className="mx-auto w-full max-w-[1440px] px-5 py-6 sm:px-8">
				<div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
					<div className="min-w-0 space-y-6">
						<section aria-label="Workspace statistics" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
							{STATS.map(({ label, value, icon: Icon }) => (
								<Card key={label} className="min-h-28 p-4">
									<div className="flex items-start justify-between gap-3">
										<span className="text-2xs font-medium uppercase tracking-[0.09em] text-ink-3">
											{label}
										</span>
										<span className="flex size-9 items-center justify-center rounded-xl bg-brand-soft text-brand">
											<Icon size={17} />
										</span>
									</div>
									<div className="mt-3 text-2xl font-semibold tracking-tight text-ink">{value}</div>
								</Card>
							))}
						</section>

						<section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_250px]">
							<Card className="p-5 sm:p-6">
								<div className="flex items-start justify-between gap-4">
									<div>
										<h2 className="text-lg font-semibold text-ink">Workspace: {workspace}</h2>
										<p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
											Engineering decisions, architecture discussions and shared knowledge for the entire team.
										</p>
									</div>
									<button type="button" aria-label="Edit workspace" className="rounded-lg p-2 text-ink-3 hover:bg-surface-2 hover:text-ink">
										<Pencil size={17} />
									</button>
								</div>

								<dl className="mt-6 grid gap-3 border-t border-line pt-5 text-[13px] sm:grid-cols-[140px_1fr]">
									<dt className="text-ink-3">Workspace URL</dt>
									<dd className="font-medium text-brand sm:text-right">memoryos.io/{workspace}</dd>
									<dt className="text-ink-3">Created</dt>
									<dd className="font-medium text-ink sm:text-right">2 days ago</dd>
									<dt className="text-ink-3">Plan</dt>
									<dd className="font-medium text-ink sm:text-right">Professional</dd>
								</dl>
							</Card>

							<Card className="p-5">
								<h2 className="text-base font-semibold text-ink">Quick actions</h2>
								<div className="mt-4 space-y-2">
									{[
										{ label: "Invite members", icon: UserPlus },
										{ label: "Add integration", icon: PlugZap },
										{ label: "View docs", icon: BookOpen },
									].map(({ label, icon: Icon }) => (
										<button key={label} type="button" className="flex w-full items-center gap-2.5 rounded-lg border border-line bg-surface-2 px-3 py-2.5 text-left text-[13px] font-medium text-ink transition-colors hover:border-line-strong hover:bg-surface-3">
											<Icon size={15} className="text-brand" />
											{label}
										</button>
									))}
								</div>
							</Card>
						</section>

						<Card className="p-5 sm:p-6">
							<div className="flex flex-wrap items-end justify-between gap-3">
								<div>
									<h2 className="text-lg font-semibold text-ink">Connected tools</h2>
									<p className="mt-1 text-[13px] text-ink-2">
										Keep engineering context synchronized across your tools.
									</p>
								</div>
								<div className="text-right">
									<div className="text-2xl font-semibold text-brand">3</div>
									<div className="text-2xs text-ink-3">of 3 connected</div>
								</div>
							</div>

							<div className="mt-5 grid gap-3 sm:grid-cols-3">
								{INTEGRATIONS.map((integration) => (
									<div key={integration.id} className="rounded-card border border-brand/35 bg-brand-soft p-4 text-center">
										<div className="flex justify-center">
											<SourceTile id={integration.id} size={44} />
										</div>
										<div className="mt-3 text-sm font-semibold text-ink">{SOURCE_BY_ID[integration.id].name}</div>
										<p className="mt-1 min-h-8 text-2xs leading-relaxed text-ink-3">{integration.description}</p>
										<div className="mt-3 inline-flex items-center gap-1.5 text-2xs font-medium text-ok">
											<CheckCircle2 size={13} />
											Connected
										</div>
									</div>
								))}
							</div>
						</Card>

						<Card className="p-5 sm:p-6">
							<h2 className="text-lg font-semibold text-ink">Recent activity</h2>
							<div className="mt-4 divide-y divide-line">
								{ACTIVITIES.map(({ id, icon: Icon, lead, detail, time }) => (
									<div key={id} className="flex flex-wrap items-center gap-3 py-4 first:pt-1 last:pb-1">
										<span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand">
											<Icon size={16} />
										</span>
										<p className="min-w-0 flex-1 text-[13px] text-ink-2">
											<strong className="font-semibold text-ink">{lead}</strong> {detail}
										</p>
										<time className="text-2xs text-ink-3">{time}</time>
									</div>
								))}
							</div>
						</Card>
					</div>

					<aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
						<label className="flex h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 text-ink-3 focus-within:border-brand focus-within:ring-2 focus-within:ring-[var(--ring)]">
							<Search size={16} />
							<input className="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-3" placeholder="Search your knowledge base…" aria-label="Search knowledge base" />
							<kbd className="rounded border border-line px-1.5 py-0.5 font-mono text-2xs">K</kbd>
						</label>

						<Card className="p-4">
							<div className="flex items-center justify-between gap-3">
								<h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
									<Activity size={16} className="text-brand" />
									Recent events
								</h2>
								<button type="button" className="text-2xs font-medium text-brand hover:underline">View all</button>
							</div>

							<div className="mt-4 space-y-2">
								{RECENT_EVENTS.map((event) => (
									<div key={event.id} className="flex items-start gap-3 rounded-lg border border-line bg-surface-2 p-3">
										<SourceTile id={event.source} size={30} />
										<div className="min-w-0">
											<p className="text-[12px] leading-relaxed text-ink">
												<strong>{SOURCE_BY_ID[event.source].name}</strong> — {event.text}
											</p>
											<time className="mt-0.5 block text-2xs text-ink-3">{event.time}</time>
										</div>
									</div>
								))}
							</div>
						</Card>

						<div className="flex items-start gap-3 rounded-card border border-brand/30 bg-brand-soft p-4">
							<span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand text-brand-ink">
								<DatabaseZap size={15} />
							</span>
							<div>
								<div className="text-[13px] font-semibold text-ink">Embeddings indexed</div>
								<div className="mt-0.5 text-2xs text-ink-2">3.2K documents · 847 queries processed</div>
							</div>
						</div>
					</aside>
				</div>
			</div>
		</>
	);
}
