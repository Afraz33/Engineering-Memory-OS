import { createContext, useContext } from "react";
import type { User } from "./api";

/**
 * Split from `auth.tsx` so that file exports only the provider component —
 * mixing components and plain values in one module breaks React Fast Refresh.
 */

export interface AuthValue {
	user: User | null;
	loading: boolean;
	signIn: (credential: string) => Promise<User>;
	signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthValue | null>(null);

export function useAuth(): AuthValue {
	const ctx = useContext(AuthContext);
	if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
	return ctx;
}
