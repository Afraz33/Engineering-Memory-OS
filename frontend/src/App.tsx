import axios from "axios";
import { useEffect, useState } from "react";

type Status = "loading" | "healthy" | "unhealthy";

const App = () => {
	const [server, setServer] = useState<Status>("loading");
	const [database, setDatabase] = useState<Status>("loading");
	const [redis, setRedis] = useState<Status>("loading");

	useEffect(() => {
		const checkHealth = async () => {
			try {
				const { data } = await axios.get("http://localhost:8000/api/health");

				setServer(data.server ? "healthy" : "unhealthy");
				setDatabase(data.database ? "healthy" : "unhealthy");
				setRedis(data.redis ? "healthy" : "unhealthy");
			} catch {
				setServer("unhealthy");
				setDatabase("unhealthy");
				setRedis("unhealthy");
			}
		};

		checkHealth();
	}, []);

	const color = (status: Status) => {
		switch (status) {
			case "healthy":
				return "text-green-400";
			case "unhealthy":
				return "text-red-400";
			default:
				return "text-yellow-400";
		}
	};

	return (
		<div className="min-h-screen bg-black flex items-center justify-center text-white">
			<div className="w-full max-w-md rounded-xl border border-white/10 bg-neutral-900 p-8 shadow-xl">
				<div className="flex flex-col items-center gap-4">
					<img
						className="h-28 w-28"
						src="https://res.cloudinary.com/dltj8bim0/image/upload/v1761060580/logo_kukwt0.png"
						alt="Logo"
					/>

					<h1 className="text-2xl font-bold">
						Engineering Memory OS
					</h1>

					<div className="mt-6 w-full space-y-4 text-lg">
						<div className="flex justify-between">
							<span>Server</span>
							<span className={color(server)}>{server}</span>
						</div>

						<div className="flex justify-between">
							<span>Database</span>
							<span className={color(database)}>{database}</span>
						</div>

						<div className="flex justify-between">
							<span>Redis</span>
							<span className={color(redis)}>{redis}</span>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

export default App;