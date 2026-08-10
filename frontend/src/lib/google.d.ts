/**
 * Minimal typings for the Google Identity Services script loaded in index.html.
 * Only the surface we actually call.
 */

interface GoogleCredentialResponse {
	credential: string;
}

interface GoogleButtonOptions {
	type?: "standard" | "icon";
	theme?: "outline" | "filled_blue" | "filled_black";
	size?: "small" | "medium" | "large";
	text?: "signin_with" | "signup_with" | "continue_with";
	shape?: "rectangular" | "pill";
	width?: number;
	logo_alignment?: "left" | "center";
}

interface GoogleAccountsId {
	initialize(config: {
		client_id: string;
		callback: (response: GoogleCredentialResponse) => void;
		auto_select?: boolean;
		cancel_on_tap_outside?: boolean;
	}): void;
	renderButton(parent: HTMLElement, options: GoogleButtonOptions): void;
	disableAutoSelect(): void;
}

declare global {
	interface Window {
		google?: {
			accounts: { id: GoogleAccountsId };
		};
	}
}

export {};
