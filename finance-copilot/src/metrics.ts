import type {
  MetricValue,
  KPICardData,
  TimeSeriesPoint,
  YoYPoint,
  RuleOf40Point,
  MarginPoint,
  CumulativeWeekData,
} from "./types";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const SHORT_MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function formatShortMonth(dateStr: string): string {
  const [year, month] = dateStr.slice(0, 10).split("-");
  return `${SHORT_MONTHS[parseInt(month, 10) - 1]} ${year}`;
}

export function calculateYoY(current: number, prior: number): number {
  if (prior === 0) return Infinity;
  return ((current - prior) / prior) * 100;
}

export function formatBillions(value: number): string {
  return (value / 1_000_000_000).toFixed(1);
}

export function formatMillions(value: number): string {
  return (value / 1_000_000).toFixed(1);
}

export function getChangeType(change: number): "increase" | "decrease" | "neutral" {
  if (change > 0) return "increase";
  if (change < 0) return "decrease";
  return "neutral";
}

export function formatPeriod(dateStr: string): string {
  const [year, month] = dateStr.split("-");
  const monthIndex = parseInt(month, 10) - 1;
  return `${MONTHS[monthIndex]} ${year}`;
}

export function buildKPICard(
  name: string,
  current: MetricValue,
  prior: MetricValue,
  unit: string
): KPICardData {
  const change = calculateYoY(current.value, prior.value);
  const changeType = getChangeType(change);
  const isBillions = unit === "$B";
  const formatted = isBillions
    ? formatBillions(current.value)
    : formatMillions(current.value);
  const displayValue = isBillions ? `${formatted} ${unit}` : `${formatted}${unit}`;
  const title = isBillions ? `${name} (in billions)` : name;
  const value = isBillions
    ? current.value / 1_000_000_000
    : current.value / 1_000_000;

  return {
    title,
    value: Math.round(value * 10) / 10,
    unit,
    displayValue,
    change: Math.round(change * 100) / 100,
    changeType,
    period: formatPeriod(current.period),
  };
}

export function calculateYoYSeries(data: TimeSeriesPoint[]): YoYPoint[] {
  if (data.length < 13) return [];

  // Sort ascending by date
  const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date));

  // Build a map of date → value for quick prior year lookup
  const byDate = new Map<string, number>();
  for (const d of sorted) {
    byDate.set(d.date.slice(0, 7), d.value);
  }

  // Get the most recent 13 months
  const recent = sorted.slice(-13);
  const result: YoYPoint[] = [];

  for (const point of recent) {
    const dateKey = point.date.slice(0, 7); // "YYYY-MM"
    const [year, month] = dateKey.split("-");
    const priorKey = `${parseInt(year) - 1}-${month}`;
    const priorValue = byDate.get(priorKey);

    if (priorValue != null && priorValue > 0) {
      result.push({
        month: formatShortMonth(point.date),
        yoy: calculateYoY(point.value, priorValue),
      });
    }
  }

  return result;
}

export function calculateRuleOf40(
  gpData: TimeSeriesPoint[],
  aoiData: TimeSeriesPoint[]
): RuleOf40Point[] {
  const yoySeries = calculateYoYSeries(gpData);
  if (yoySeries.length === 0) return [];

  // Build AOI map and GP map by date for margin calc
  const gpByMonth = new Map<string, number>();
  for (const d of gpData) gpByMonth.set(formatShortMonth(d.date), d.value);

  const aoiByMonth = new Map<string, number>();
  for (const d of aoiData) aoiByMonth.set(formatShortMonth(d.date), d.value);

  const result: RuleOf40Point[] = [];
  for (const yoy of yoySeries) {
    const gp = gpByMonth.get(yoy.month);
    const aoi = aoiByMonth.get(yoy.month);
    if (gp != null && gp > 0 && aoi != null) {
      const opMargin = (aoi / gp) * 100;
      result.push({
        month: yoy.month,
        gpYoY: yoy.yoy,
        opMargin,
        ruleOf40: yoy.yoy + opMargin,
      });
    }
  }

  return result;
}

export function calculateMarginSeries(
  aoiData: TimeSeriesPoint[],
  gpData: TimeSeriesPoint[]
): MarginPoint[] {
  const gpByDate = new Map<string, number>();
  for (const d of gpData) gpByDate.set(d.date.slice(0, 7), d.value);

  const sorted = [...aoiData].sort((a, b) => a.date.localeCompare(b.date));
  const result: MarginPoint[] = [];

  for (const point of sorted) {
    const dateKey = point.date.slice(0, 7);
    const gp = gpByDate.get(dateKey);
    if (gp != null && gp > 0) {
      result.push({
        month: formatShortMonth(point.date),
        aoi: point.value,
        margin: (point.value / gp) * 100,
      });
    }
  }

  return result;
}

export function buildCumulativeWeeks(
  dailyData: TimeSeriesPoint[]
): CumulativeWeekData[] {
  if (dailyData.length === 0) return [];

  // Sort ascending
  const sorted = [...dailyData].sort((a, b) => a.date.localeCompare(b.date));

  // Group by ISO week (Mon-Sun)
  const weeks = new Map<string, { day: number; value: number }[]>();
  for (const point of sorted) {
    const d = new Date(point.date + "T00:00:00");
    // Get Monday of this week
    const dayOfWeek = d.getDay(); // 0=Sun, 1=Mon
    const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    const monday = new Date(d);
    monday.setDate(d.getDate() + mondayOffset);
    const weekKey = monday.toISOString().slice(0, 10);

    if (!weeks.has(weekKey)) weeks.set(weekKey, []);
    weeks.get(weekKey)!.push({ day: dayOfWeek === 0 ? 6 : dayOfWeek - 1, value: point.value });
  }

  // Get week labels sorted (most recent last)
  const weekKeys = [...weeks.keys()].sort();
  const labels = weekKeys.map((k) => {
    const d = new Date(k + "T00:00:00");
    return `Week of ${SHORT_MONTHS[d.getMonth()]} ${d.getDate()}`;
  });

  // Build 7-row result (Mon-Sun), one column per week with cumulative sums
  const result: CumulativeWeekData[] = [];
  for (let dayIdx = 0; dayIdx < 7; dayIdx++) {
    const row: CumulativeWeekData = { dayOfWeek: DAY_NAMES[dayIdx === 6 ? 0 : dayIdx + 1] };
    // Fix: dayIdx 0=Mon, 1=Tue, ..., 6=Sun

    for (let wi = 0; wi < weekKeys.length; wi++) {
      const weekDays = weeks.get(weekKeys[wi])!;
      let cumulative = 0;
      for (let d = 0; d <= dayIdx; d++) {
        const found = weekDays.find((wd) => wd.day === d);
        if (found) cumulative += found.value;
      }
      row[labels[wi]] = cumulative > 0 ? cumulative : 0;
    }

    result.push(row);
  }

  return result;
}
