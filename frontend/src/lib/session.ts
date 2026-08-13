import { useCallback, useEffect, useState } from "react";
import type { SourceId, Tier } from "./types";

/**
 * Client-side session/onboarding state.
 *
 * Deliberately a thin localStorage shim: the backend auth endpoints don't
 * exist yet, and every consumer here reads through `useSession`, so swapping
 * this for real API calls is a one-file change.
 */

const KEY = "ems.session";

export interface SessionState {
	email: string | null;
	/** Cosmetic device/install label — not the backend workspace name. */
	label: string;
	sources: SourceId[];
	tiers: Tier[];
	deployment: "local" | "cloud";
}

const EMPTY: SessionState = {
	email: null,
	label: "",
	sources: [],
	tiers: ["identity", "project", "decision"],
	deployment: "local",
};

function read(): SessionState {
	try {
		const raw = localStorage.getItem(KEY);
		return raw ? { ...EMPTY, ...(JSON.parse(raw) as SessionState) } : EMPTY;
	} catch {
		return EMPTY;
	}
}

function write(next: SessionState) {
	localStorage.setItem(KEY, JSON.stringify(next));
	window.dispatchEvent(new Event("ems:session"));
}

export function useSession() {
	const [state, setState] = useState<SessionState>(read);

	useEffect(() => {
		const sync = () => setState(read());
		window.addEventListener("ems:session", sync);
		window.addEventListener("storage", sync);
		return () => {
			window.removeEventListener("ems:session", sync);
			window.removeEventListener("storage", sync);
		};
	}, []);

	const patch = useCallback((next: Partial<SessionState>) => {
		write({ ...read(), ...next });
	}, []);

	const signOut = useCallback(() => {
		localStorage.removeItem(KEY);
		window.dispatchEvent(new Event("ems:session"));
	}, []);

	return { session: state, patch, signOut };
}

/* ── theme ─────────────────────────────────────────────────────────── */

const THEME_KEY = "ems.theme";
export type Theme = "dark" | "light";

export function initTheme() {
	const stored = localStorage.getItem(THEME_KEY) as Theme | null;
	const theme: Theme =
		stored ??
		(window.matchMedia?.("(prefers-color-scheme: light)").matches
			? "light"
			: "dark");
	document.documentElement.dataset.theme = theme;
}

export function useTheme() {
	const [theme, setTheme] = useState<Theme>(
		() => (document.documentElement.dataset.theme as Theme) ?? "dark",
	);

	const toggle = useCallback(() => {
		setTheme((current) => {
			const next: Theme = current === "dark" ? "light" : "dark";
			document.documentElement.dataset.theme = next;
			localStorage.setItem(THEME_KEY, next);
			return next;
		});
	}, []);

	return { theme, toggle };
}
