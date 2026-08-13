import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.tsx";
import "./index.css";
import { AuthProvider } from "./lib/auth";
import { initTheme } from "./lib/session";
import { WorkspaceProvider } from "./lib/workspace";

initTheme();

createRoot(document.getElementById("root")!).render(
	<StrictMode>
		<BrowserRouter>
			<AuthProvider>
				<WorkspaceProvider>
					<App />
				</WorkspaceProvider>
			</AuthProvider>
		</BrowserRouter>
	</StrictMode>,
);
