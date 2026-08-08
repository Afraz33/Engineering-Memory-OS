/**
 * The four memory tiers. This is the core abstraction of the product:
 * every captured item is classified into exactly one, and retrieval
 * weights them differently (identity always in context, session almost
 * never). Ordering here is the canonical display order.
 */
export const TIERS = ["identity", "project", "session", "decision"] as const;
export type Tier = (typeof TIERS)[number];

export const TIER_META: Record<
	Tier,
	{ label: string; blurb: string; retention: string; className: string }
> = {
	identity: {
		label: "Identity",
		blurb: "Who you are, how you work, standing preferences and constraints.",
		retention: "Never expires",
		className: "text-identity",
	},
	project: {
		label: "Project",
		blurb: "Goals, scope and state for an area of work or a repository.",
		retention: "Lives with the project",
		className: "text-project",
	},
	session: {
		label: "Session",
		blurb: "Working details from one conversation. Cheap to forget.",
		retention: "Decays in 14 days",
		className: "text-session",
	},
	decision: {
		label: "Decision",
		blurb: "A choice that was made, why, and what it supersedes.",
		retention: "Permanent, versioned",
		className: "text-decision",
	},
};

export type SourceId =
	| "github"
	| "slack"
	| "jira"
	| "notion"
	| "linear"
	| "claude-code"
	| "chatgpt"
	| "codex"
	| "obsidian";

export type SourceKind = "code" | "chat" | "docs" | "agent";

export interface SourceDef {
	id: SourceId;
	name: string;
	kind: SourceKind;
	/** What this source is actually good for — shown during onboarding. */
	captures: string;
	accent: string;
	available: boolean;
}

export interface Connection {
	id: SourceId;
	status: "connected" | "syncing" | "error" | "idle";
	items: number;
	lastSync: string;
}

export interface MemoryItem {
	id: string;
	tier: Tier;
	title: string;
	body: string;
	source: SourceId;
	sourceLabel: string;
	space: string;
	updated: string;
	/** id of the memory this one replaced, if any */
	supersedes?: string;
	supersededBy?: string;
	confidence: number;
}

export interface Space {
	id: string;
	name: string;
	color: string;
	count: number;
}
