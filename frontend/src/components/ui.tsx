import type {
	ButtonHTMLAttributes,
	InputHTMLAttributes,
	ReactNode,
} from "react";
import { cx } from "../lib/cx";
import { TIER_META, type Tier } from "../lib/types";

/* ── Button ────────────────────────────────────────────────────────── */

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANT: Record<Variant, string> = {
	primary:
		"bg-brand text-brand-ink hover:bg-brand-hover shadow-sm disabled:bg-brand/40",
	secondary:
		"bg-surface-2 text-ink border border-line hover:bg-surface-3 hover:border-line-strong",
	ghost: "text-ink-2 hover:text-ink hover:bg-surface-2",
	danger: "bg-danger/12 text-danger border border-danger/30 hover:bg-danger/20",
};

const SIZE: Record<Size, string> = {
	sm: "h-8 px-3 text-[13px] gap-1.5 rounded-lg",
	md: "h-10 px-4 text-sm gap-2 rounded-lg",
	lg: "h-11 px-5 text-[15px] gap-2 rounded-xl",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
	variant?: Variant;
	size?: Size;
	full?: boolean;
}

export function Button({
	variant = "primary",
	size = "md",
	full,
	className,
	...rest
}: ButtonProps) {
	return (
		<button
			className={cx(
				"inline-flex items-center justify-center font-medium transition-colors duration-150",
				"disabled:cursor-not-allowed disabled:opacity-60",
				VARIANT[variant],
				SIZE[size],
				full && "w-full",
				className,
			)}
			{...rest}
		/>
	);
}

/* ── Field ─────────────────────────────────────────────────────────── */

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
	label: string;
	hint?: string;
	icon?: ReactNode;
}

export function Field({ label, hint, icon, className, id, ...rest }: FieldProps) {
	const inputId = id ?? `f-${label.toLowerCase().replace(/\s+/g, "-")}`;
	return (
		<div className="space-y-1.5">
			<label
				htmlFor={inputId}
				className="block text-[13px] font-medium text-ink-2"
			>
				{label}
			</label>
			<div className="relative">
				{icon && (
					<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3">
						{icon}
					</span>
				)}
				<input
					id={inputId}
					className={cx(
						"h-10 w-full rounded-lg border border-line bg-surface-2 text-sm text-ink",
						"placeholder:text-ink-3 transition-colors",
						"hover:border-line-strong focus:border-brand focus:outline-none focus:ring-2 focus:ring-[var(--ring)]",
						icon ? "pl-9 pr-3" : "px-3",
						className,
					)}
					{...rest}
				/>
			</div>
			{hint && <p className="text-2xs text-ink-3">{hint}</p>}
		</div>
	);
}

/* ── Card ──────────────────────────────────────────────────────────── */

export function Card({
	children,
	className,
	interactive,
}: {
	children: ReactNode;
	className?: string;
	interactive?: boolean;
}) {
	return (
		<div
			className={cx(
				"rounded-card border border-line bg-surface",
				interactive &&
					"transition-colors duration-150 hover:border-line-strong hover:bg-surface-2",
				className,
			)}
		>
			{children}
		</div>
	);
}

/* ── Tier badge ────────────────────────────────────────────────────── */

const TIER_DOT: Record<Tier, string> = {
	identity: "bg-identity",
	project: "bg-project",
	session: "bg-session",
	decision: "bg-decision",
};

export function TierBadge({ tier, size = "md" }: { tier: Tier; size?: "sm" | "md" }) {
	return (
		<span
			className={cx(
				"inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-2 font-medium",
				size === "sm" ? "px-1.5 py-0.5 text-2xs" : "px-2 py-1 text-xs",
				TIER_META[tier].className,
			)}
		>
			<span className={cx("size-1.5 rounded-full", TIER_DOT[tier])} />
			{TIER_META[tier].label}
		</span>
	);
}

/* ── Status dot ────────────────────────────────────────────────────── */

export function StatusDot({
	status,
}: {
	status: "connected" | "syncing" | "error" | "idle";
}) {
	const tone =
		status === "connected"
			? "bg-ok"
			: status === "syncing"
				? "bg-warn"
				: status === "error"
					? "bg-danger"
					: "bg-ink-3";
	return (
		<span className="relative flex size-2" title={status}>
			{status === "syncing" && (
				<span className={cx("absolute inline-flex size-2 animate-ping rounded-full opacity-70", tone)} />
			)}
			<span className={cx("relative inline-flex size-2 rounded-full", tone)} />
		</span>
	);
}

/* ── Section heading used across settings/onboarding ───────────────── */

export function SectionTitle({
	title,
	description,
}: {
	title: string;
	description?: string;
}) {
	return (
		<div className="space-y-1">
			<h2 className="text-base font-semibold text-ink">{title}</h2>
			{description && (
				<p className="text-[13px] leading-relaxed text-ink-2">{description}</p>
			)}
		</div>
	);
}
