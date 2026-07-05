export function parseChartDate(value: string | Date): Date | null {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  const rawValue = String(value);
  const [year, month, day] = rawValue
    .slice(0, 10)
    .split("-")
    .map(Number);

  if (!year || !month || !day) {
    const parsed = new Date(rawValue);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  return new Date(year, month - 1, day);
}

const monthLabels = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

function twoDigit(value: number) {
  return String(value).padStart(2, "0");
}

export function formatChartDateTick(
  value: string | Date,
  options: {
    compact?: boolean;
    includeYear?: boolean;
    monthOnly?: boolean;
  } = {},
): string {
  const date = parseChartDate(value);
  if (!date) {
    return String(value);
  }

  if (options.monthOnly) {
    return `${monthLabels[date.getMonth()]} ${date.getFullYear()}`;
  }

  if (options.compact) {
    return `${twoDigit(date.getDate())}.${twoDigit(date.getMonth() + 1)}`;
  }

  const label = `${twoDigit(date.getDate())} ${monthLabels[date.getMonth()]}`;
  return options.includeYear ? `${label} ${date.getFullYear()}` : label;
}

export function formatChartDateTooltip(value: string | Date): string {
  const date = parseChartDate(value);
  if (!date) {
    return String(value);
  }

  return `${twoDigit(date.getDate())} ${
    monthLabels[date.getMonth()]
  } ${date.getFullYear()}`;
}

export function isDateLikeChartValue(value: unknown): boolean {
  if (value instanceof Date) {
    return !Number.isNaN(value.getTime());
  }

  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value);
}
