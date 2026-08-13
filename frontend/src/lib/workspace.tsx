import { type ReactNode, useCallback, useEffect, useState } from "react";
import {
	fetchWorkspace,
	fetchWorkspaces,
	switchWorkspace,
	type Workspace,
	type WorkspaceSummary,
} from "./api";
import { useAuth } from "./auth-context";
import { WorkspaceContext } from "./workspace-context";

/**
 * The signed-in user's active workspace (name, role, members) plus the full
 * list they belong to, for the switcher.
 *
 * Keyed off `useAuth().user`: fetches once a user is present, resets to null
 * on sign-out. Deliberately separate from `AuthProvider` — it needs `user.id`
 * to know *when* to fetch, so it has to live inside `<AuthProvider>`.
 */
export function WorkspaceProvider({ children }: { children: ReactNode }) {
	const { user } = useAuth();
	const [workspace, setWorkspace] = useState<Workspace | null>(null);
	const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
	// Which user id `workspace`/`workspaces` reflect. Comparing this to `user.id`
	// at render time (rather than a `useState(true/false)` flag flipped inside
	// the effect) is what makes `loading` correct on the very first render right
	// after sign-in: a plain flag stays stale at `false` — left over from the
	// signed-out effect run — until the effect fires, which is one render too
	// late and lets the router briefly treat a returning user as unonboarded.
	const [fetchedForUserId, setFetchedForUserId] = useState<string | null>(null);
	const loading = !!user && fetchedForUserId !== user.id;

	const load = useCallback(async () => {
		const [active, all] = await Promise.all([fetchWorkspace(), fetchWorkspaces()]);
		setWorkspace(active);
		setWorkspaces(all);
	}, []);

	useEffect(() => {
		if (!user) {
			setWorkspace(null);
			setWorkspaces([]);
			setFetchedForUserId(null);
			return;
		}

		let alive = true;
		load().finally(() => {
			if (alive) setFetchedForUserId(user.id);
		});
		return () => {
			alive = false;
		};
	}, [user, load]);

	const switchTo = useCallback(
		async (workspaceId: string) => {
			await switchWorkspace(workspaceId);
			await load();
		},
		[load],
	);

	return (
		<WorkspaceContext.Provider
			value={{ workspace, workspaces, loading, refresh: load, switchTo }}
		>
			{children}
		</WorkspaceContext.Provider>
	);
}
