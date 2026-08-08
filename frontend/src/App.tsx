import { Navigate, Route, Routes } from "react-router-dom";
import AppShell from "./layouts/AppShell";
import { useSession } from "./lib/session";
import Ask from "./pages/Ask";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Memory from "./pages/Memory";
import Onboarding from "./pages/Onboarding";
import Settings from "./pages/Settings";
import Sources from "./pages/Sources";
import Team from "./pages/Team";
import Timeline from "./pages/Timeline";

const App = () => {
	const { session } = useSession();

	return (
		<Routes>
			<Route path="/" element={<Login />} />
			<Route path="/welcome" element={<Login />} />
			<Route path="/login" element={<Login />} />
			<Route
				path="/onboarding"
				element={session.email ? <Onboarding /> : <Navigate to="/login" replace />}
			/>

			<Route element={<AppShell />}>
				<Route path="/dashboard" element={<Dashboard />} />
				<Route path="/connections" element={<Sources />} />
				<Route path="/team" element={<Team />} />
				<Route path="/memory" element={<Memory />} />
				<Route path="/timeline" element={<Timeline />} />
				<Route path="/ask" element={<Ask />} />
				<Route path="/sources" element={<Sources />} />
				<Route path="/settings" element={<Settings />} />
			</Route>

			<Route
				path="*"
				element={
					<Navigate
						to={session.email && session.onboarded ? "/dashboard" : "/welcome"}
						replace
					/>
				}
			/>
		</Routes>
	);
};

export default App;
