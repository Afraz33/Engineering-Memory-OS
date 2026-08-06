import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./layouts/AppShell";
import { useSession } from "./lib/session";
import Ask from "./pages/Ask";
import Login from "./pages/Login";
import Memory from "./pages/Memory";
import Onboarding from "./pages/Onboarding";
import Settings from "./pages/Settings";
import Sources from "./pages/Sources";
import Timeline from "./pages/Timeline";

const App = () => {
	const { session } = useSession();

	return (
		<Routes>
			<Route
				path="/login"
				element={
					session.email && session.onboarded ? (
						<Navigate to="/memory" replace />
					) : (
						<Login />
					)
				}
			/>
			<Route path="/onboarding" element={<Onboarding />} />

			<Route element={<AppShell />}>
				<Route path="/memory" element={<Memory />} />
				<Route path="/timeline" element={<Timeline />} />
				<Route path="/ask" element={<Ask />} />
				<Route path="/sources" element={<Sources />} />
				<Route path="/settings" element={<Settings />} />
			</Route>

			<Route
				path="*"
				element={
					<Navigate to={session.onboarded ? "/memory" : "/login"} replace />
				}
			/>
		</Routes>
	);
};

export default App;
