import { createContext, useContext } from "react";
import type { Workspace, WorkspaceSummary } from "./api";

/**
 * Split from `workspace.tsx` so that file exports only the provider component —
 * mixing components and plain values in one module breaks React Fast Refresh.
 */

export interface WorkspaceValue {
	workspace: Workspace | null;
	/** Every workspace the user belongs to, for the switcher. */
	workspaces: WorkspaceSummary[];
	loading: boolean;
	refresh: () => Promise<void>;
	switchTo: (workspaceId: string) => Promise<void>;
}

export const WorkspaceContext = createContext<WorkspaceValue | null>(null);

export function useWorkspace(): WorkspaceValue {
	const ctx = useContext(WorkspaceContext);
	if (!ctx) throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
	return ctx;
}
