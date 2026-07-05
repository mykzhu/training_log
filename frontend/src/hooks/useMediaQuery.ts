import { useEffect, useState } from "react";

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    setMatches(media.matches);

    const listener = () => setMatches(media.matches);
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [query]);

  return matches;
}

export function getResponsiveXAxisProps(
  pointCount: number,
  isSmallScreen: boolean,
) {
  if (!isSmallScreen) {
    return {
      angle: 0,
      textAnchor: "middle" as const,
      interval: "preserveStartEnd" as const,
      height: 36,
    };
  }

  if (pointCount <= 6) {
    return {
      angle: 0,
      textAnchor: "middle" as const,
      interval: 0,
      height: 36,
    };
  }

  if (pointCount <= 12) {
    return {
      angle: -45,
      textAnchor: "end" as const,
      interval: 0,
      height: 56,
    };
  }

  return {
    angle: -65,
    textAnchor: "end" as const,
    interval: "preserveStartEnd" as const,
    height: 72,
  };
}
