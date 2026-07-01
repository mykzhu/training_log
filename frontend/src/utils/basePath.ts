export function normalizeBasePath(value: string): string {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "/") {
    return "";
  }

  return `/${trimmed.replace(/^\/+|\/+$/g, "")}`;
}

export function detectIngressBasePath(
  pathname = window.location.pathname,
): string {
  const segments = pathname.split("/").filter(Boolean);

  if (
    segments[0] === "api" &&
    segments[1] === "hassio_ingress" &&
    segments[2]
  ) {
    return `/${segments.slice(0, 3).join("/")}`;
  }

  return "";
}

export function appBasePath(): string {
  const configured = import.meta.env.VITE_APP_BASE_PATH;
  if (typeof configured === "string" && configured.trim()) {
    return normalizeBasePath(configured);
  }

  return detectIngressBasePath();
}

export function withAppBasePath(path: string): string {
  if (!path) {
    return appBasePath() || "/";
  }
  if (/^[a-z][a-z0-9+.-]*:/i.test(path)) {
    return path;
  }

  const base = appBasePath();
  if (!base) {
    return path;
  }

  if (path.startsWith("/")) {
    return `${base}${path}`;
  }

  return `${base}/${path}`;
}
