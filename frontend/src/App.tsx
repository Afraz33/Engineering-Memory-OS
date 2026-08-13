import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./layouts/AppShell";
import { useAuth } from "./lib/auth-context";
import { useWorkspace } from "./lib/workspace-context";
import Ask from "./pages/Ask";
import Login from "./pages/Login";
import Memory from "./pages/Memory";
import Onboarding from "./pages/Onboarding";
import Settings from "./pages/Settings";
import Sources from "./pages/Sources";
import Timeline from "./pages/Timeline";

/** Shown for the one round trip it takes to ask the server who we are. */
export const Splash = () => (
	<div className="grid min-h-screen place-items-center bg-surface">
		<div className="size-5 animate-spin rounded-full border-2 border-line border-t-brand" />
	</div>
);

const RequireAuth = ({ children }: { children: ReactNode }) => {
	const { user, loading } = useAuth();
	if (loading) return <Splash />;
	return user ? <>{children}</> : <Navigate to="/login" replace />;
};

const App = () => {
	const { user, loading } = useAuth();
	const { workspace, loading: workspaceLoading } = useWorkspace();

	// Route gating is driven entirely by server state: `user` (server-verified
	// session) and `workspace` (does this account have one yet). Neither lives
	// in localStorage, so a fresh browser or device lands in the same place a
	// returning user would -- onboarding only shows once, at the workspace's
	// actual creation, not on every login.
	const home = workspace ? "/memory" : "/onboarding";

	if (loading) return <Splash />;
	if (user && workspaceLoading) return <Splash />;

	return (
		<Routes>
			<Route
				path="/login"
				element={user ? <Navigate to={home} replace /> : <Login />}
			/>
			<Route
				path="/onboarding"
				element={
					<RequireAuth>
						<Onboarding />
					</RequireAuth>
				}
			/>

			<Route
				element={
					<RequireAuth>
						<AppShell />
					</RequireAuth>
				}
			>
				<Route path="/memory" element={<Memory />} />
				<Route path="/timeline" element={<Timeline />} />
				<Route path="/ask" element={<Ask />} />
				<Route path="/sources" element={<Sources />} />
				<Route path="/settings" element={<Settings />} />
			</Route>

			<Route
				path="*"
				element={<Navigate to={user ? home : "/login"} replace />}
			/>
		</Routes>
	);
};

export default App;
