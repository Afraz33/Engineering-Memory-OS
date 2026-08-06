/** Join class names, dropping falsy values. */
export function cx(...parts: (string | false | null | undefined)[]) {
	return parts.filter(Boolean).join(" ");
}
