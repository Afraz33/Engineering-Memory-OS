import { Crown, Mail, UserPlus } from "lucide-react";
import { Button, Card } from "../components/ui";
import { useSession } from "../lib/session";

const TEAM = [
	{
		id: "member-1",
		name: "Felix Dev",
		email: "felix.dev@acme.io",
		role: "Owner",
		initials: "FD",
	},
	{
		id: "member-2",
		name: "Alex Rodriguez",
		email: "alex@acme.io",
		role: "Member",
		initials: "AR",
	},
];

export default function Team() {
	const { session } = useSession();
	const members = TEAM.map((member, index) =>
		index === 0 && session.email
			? { ...member, email: session.email }
			: member,
	);

	return (
		<>
			<header className="flex flex-wrap items-center gap-4 border-b border-line px-6 py-5 sm:px-8">
				<div className="min-w-0 flex-1">
					<h1 className="display text-xl text-ink">Team</h1>
					<p className="mt-1 text-[13px] text-ink-2">
						Manage who can access this workspace.
					</p>
				</div>
				<Button>
					<UserPlus size={16} />
					Invite member
				</Button>
			</header>

			<div className="mx-auto w-full max-w-4xl px-6 py-6 sm:px-8">
				<Card className="overflow-hidden">
					<div className="border-b border-line px-5 py-4">
						<h2 className="text-base font-semibold text-ink">Workspace members</h2>
						<p className="mt-1 text-2xs text-ink-3">2 people have access.</p>
					</div>

					<div className="divide-y divide-line">
						{members.map((member) => (
							<div key={member.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
								<span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-brand-soft text-[13px] font-semibold text-brand">
									{member.initials}
								</span>
								<div className="min-w-0 flex-1">
									<div className="flex items-center gap-2">
										<span className="text-sm font-medium text-ink">{member.name}</span>
										{member.role === "Owner" && <Crown size={13} className="text-brand" />}
									</div>
									<div className="mt-0.5 flex items-center gap-1.5 text-2xs text-ink-3">
										<Mail size={12} />
										{member.email}
									</div>
								</div>
								<span className="rounded-lg border border-line bg-surface-2 px-2.5 py-1 text-2xs font-medium text-ink-2">
									{member.role}
								</span>
							</div>
						))}
					</div>
				</Card>
			</div>
		</>
	);
}
