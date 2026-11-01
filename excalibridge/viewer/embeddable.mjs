// Keep local prototypes separate from Excalidraw's built-in provider allowlist.
export function localEmbedURL(link, origin) {
  if (typeof link !== "string" || !link || /[\\\u0000-\u0020]/.test(link)) return null;
  try {
    const url = new URL(link, origin);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return null;
    const path = decodeURIComponent(url.pathname);
    if (path.startsWith("/_excalibridge/") || path.split("/").includes("..")) return null;
    if (url.origin === origin) return /\.html?$/i.test(path) ? url.href : null;
    // Relative links must refer to a project HTML file; dev-server URLs must be explicit.
    if (!/^https?:\/\//i.test(link)) return null;
    return ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) ? url.href : null;
  } catch {
    return null;
  }
}
