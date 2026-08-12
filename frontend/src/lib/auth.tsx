import { type ReactNode, useCallback, useEffect, useState } from "react";
import { fetchMe, loginWithGoogle, logout as apiLogout, type User } from "./api";
import { AuthContext } from "./auth-context";

/**
 * Who is signed in, according to the server.
 *
 * The auth cookie is HttpOnly, so the browser cannot read it — the only way to
 * know whether a session is live is to ask. That single `fetchMe()` on mount is
 * what makes a reload keep you logged in, and it is also why `loading` matters:
 * until it resolves we genuinely do not know, and routing on "not signed in"
 * too early would bounce a signed-in user to /login on every refresh.
 *
 * Deliberately separate from `useSession` (localStorage), which holds UI and
 * onboarding preferences the server has no opinion about.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
	const [user, setUser] = useState<User | null>(null);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		let alive = true;
		fetchMe()
			.then((u) => {
				if (alive) setUser(u);
			})
			.finally(() => {
				if (alive) setLoading(false);
			});
		return () => {
			alive = false;
		};
	}, []);

	const signIn = useCallback(async (credential: string) => {
		const next = await loginWithGoogle(credential);
		setUser(next);
		return next;
	}, []);

	const signOut = useCallback(async () => {
		// Clear locally even if the request fails — the user asked to leave, and
		// a stale cookie is less bad than a UI that refuses to sign out.
		try {
			await apiLogout();
		} finally {
			setUser(null);
		}
	}, []);

	return (
		<AuthContext.Provider value={{ user, loading, signIn, signOut }}>
			{children}
		</AuthContext.Provider>
	);
}
