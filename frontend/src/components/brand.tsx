import {
	Braces,
	FileText,
	Gem,
	GitPullRequest,
	Hash,
	Layers,
	MessageCircle,
	Terminal,
} from "lucide-react";
import type { ComponentType } from "react";
import { SOURCE_BY_ID } from "../lib/data";
import type { SourceId } from "../lib/types";
import { cx } from "../lib/cx";

/**
 * Logo mark — three stacked context layers converging on one node.
 * Inline SVG so it themes with the app and needs no network round trip
 * (the product claims to run offline; the logo should too).
 */
export function Mark({ size = 28 }: { size?: number }) {
	return (
		<svg
			width={size}
			height={size}
			viewBox="0 0 32 32"
			fill="none"
			aria-hidden="true"
			className="shrink-0"
		>
			<rect width="32" height="32" rx="8" fill="var(--brand)" />
			<path
				d="M8 11.5 16 7l8 4.5"
				stroke="var(--brand-ink)"
				strokeWidth="1.9"
				strokeLinecap="round"
				strokeLinejoin="round"
				opacity="0.45"
			/>
			<path
				d="M8 16 16 11.5 24 16"
				stroke="var(--brand-ink)"
				strokeWidth="1.9"
				strokeLinecap="round"
				strokeLinejoin="round"
				opacity="0.7"
			/>
			<path
				d="M8 20.5 16 16l8 4.5-8 4.5-8-4.5Z"
				stroke="var(--brand-ink)"
				strokeWidth="1.9"
				strokeLinecap="round"
				strokeLinejoin="round"
			/>
			<circle cx="16" cy="20.5" r="1.9" fill="var(--brand-ink)" />
		</svg>
	);
}

export function Wordmark({
	size = 28,
	sub,
}: {
	size?: number;
	sub?: string;
}) {
	return (
		<div className="flex items-center gap-2.5">
			<Mark size={size} />
			<div className="leading-tight">
				<div className="wordmark text-[15px] text-ink">Memory OS</div>
				{sub && <div className="text-2xs text-ink-3">{sub}</div>}
			</div>
		</div>
	);
}

/* ── Source tiles ──────────────────────────────────────────────────── */

const GLYPH: Record<SourceId, ComponentType<{ size?: number; strokeWidth?: number }>> = {
	github: GitPullRequest,
	slack: Hash,
	notion: FileText,
	linear: Layers,
	"claude-code": Terminal,
	chatgpt: MessageCircle,
	codex: Braces,
	obsidian: Gem,
};

export function SourceTile({
	id,
	size = 32,
	muted,
}: {
	id: SourceId;
	size?: number;
	muted?: boolean;
}) {
	const Glyph = GLYPH[id];
	const accent = SOURCE_BY_ID[id]?.accent ?? "var(--ink-2)";
	return (
		<span
			className={cx(
				"inline-flex items-center justify-center rounded-lg border",
				muted ? "opacity-50" : "",
			)}
			style={{
				width: size,
				height: size,
				background: `color-mix(in oklab, ${accent} 14%, transparent)`,
				borderColor: `color-mix(in oklab, ${accent} 28%, transparent)`,
				color: accent,
			}}
		>
			<Glyph size={Math.round(size * 0.5)} strokeWidth={1.9} />
		</span>
	);
}

/**
 * Marketing illustration: sources on the left feeding a tiered memory
 * spine, which feeds agents on the right. Replaces the stock logo image
 * that used to sit on the health screen.
 */
export function ContextGraph({ className }: { className?: string }) {
	const sources: SourceId[] = ["github", "slack", "notion", "chatgpt"];
	const agents: SourceId[] = ["claude-code", "codex"];

	return (
		<svg
			viewBox="0 0 420 300"
			className={className}
			fill="none"
			role="img"
			aria-label="Sources flowing into a tiered memory layer, then out to AI agents"
		>
			<defs>
				<linearGradient id="flow-in" x1="0" x2="1">
					<stop offset="0%" stopColor="var(--tier-project)" stopOpacity="0.08" />
					<stop offset="100%" stopColor="var(--tier-project)" stopOpacity="0.55" />
				</linearGradient>
				<linearGradient id="flow-out" x1="0" x2="1">
					<stop offset="0%" stopColor="var(--brand)" stopOpacity="0.55" />
					<stop offset="100%" stopColor="var(--brand)" stopOpacity="0.08" />
				</linearGradient>
			</defs>

			{/* inbound edges */}
			{sources.map((_, i) => (
				<path
					key={`in-${i}`}
					d={`M78 ${52 + i * 66} C 130 ${52 + i * 66}, 150 150, 186 150`}
					stroke="url(#flow-in)"
					strokeWidth="1.5"
					strokeDasharray="4 8"
					style={{ animation: `ems-dash ${3 + i * 0.4}s linear infinite` }}
				/>
			))}

			{/* outbound edges */}
			{agents.map((_, i) => (
				<path
					key={`out-${i}`}
					d={`M234 150 C 272 150, 292 ${106 + i * 88}, 344 ${106 + i * 88}`}
					stroke="url(#flow-out)"
					strokeWidth="1.5"
					strokeDasharray="4 8"
					style={{ animation: `ems-dash ${2.6 + i * 0.5}s linear infinite` }}
				/>
			))}

			{/* source nodes */}
			{sources.map((id, i) => (
				<g key={id} transform={`translate(46, ${36 + i * 66})`}>
					<rect
						width="32"
						height="32"
						rx="9"
						fill="var(--surface-2)"
						stroke="var(--line-strong)"
					/>
					<circle
						cx="16"
						cy="16"
						r="4.5"
						fill={SOURCE_BY_ID[id].accent}
						style={{ animation: `ems-pulse-node ${2.4 + i * 0.3}s ease-in-out infinite` }}
					/>
				</g>
			))}

			{/* memory spine — four tiers */}
			<rect
				x="186"
				y="62"
				width="48"
				height="176"
				rx="14"
				fill="var(--surface-2)"
				stroke="var(--line-strong)"
			/>
			{[
				"var(--tier-identity)",
				"var(--tier-project)",
				"var(--tier-session)",
				"var(--tier-decision)",
			].map((c, i) => (
				<rect
					key={c}
					x="198"
					y={80 + i * 40}
					width="24"
					height="24"
					rx="7"
					fill={`color-mix(in oklab, ${c} 26%, transparent)`}
					stroke={c}
					strokeWidth="1.4"
				/>
			))}

			{/* agent nodes */}
			{agents.map((id, i) => (
				<g key={id} transform={`translate(344, ${90 + i * 88})`}>
					<rect
						width="32"
						height="32"
						rx="9"
						fill="var(--surface-2)"
						stroke="var(--line-strong)"
					/>
					<circle
						cx="16"
						cy="16"
						r="4.5"
						fill="var(--brand)"
						style={{ animation: `ems-pulse-node ${2 + i * 0.4}s ease-in-out infinite` }}
					/>
				</g>
			))}
		</svg>
	);
}
