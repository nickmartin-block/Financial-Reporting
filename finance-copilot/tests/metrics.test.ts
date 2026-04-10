import { describe, it, expect } from "vitest";
import {
  calculateYoY,
  formatBillions,
  formatMillions,
  getChangeType,
  buildKPICard,
  formatPeriod,
  calculateYoYSeries,
  calculateRuleOf40,
  calculateMarginSeries,
  buildCumulativeWeeks,
} from "../src/metrics";

describe("calculateYoY", () => {
  it("calculates positive YoY percentage change", () => {
    const result = calculateYoY(45_200_000_000, 42_100_000_000);
    expect(result).toBeCloseTo(7.36, 1);
  });

  it("calculates negative YoY percentage change", () => {
    const result = calculateYoY(40_000_000_000, 42_000_000_000);
    expect(result).toBeCloseTo(-4.76, 1);
  });

  it("returns 0 when values are equal", () => {
    expect(calculateYoY(100, 100)).toBe(0);
  });

  it("returns Infinity when prior is 0", () => {
    expect(calculateYoY(100, 0)).toBe(Infinity);
  });
});

describe("formatBillions", () => {
  it("formats large numbers as billions with 1 decimal", () => {
    expect(formatBillions(45_200_000_000)).toBe("45.2");
  });

  it("formats exact billions", () => {
    expect(formatBillions(10_000_000_000)).toBe("10.0");
  });

  it("formats sub-billion", () => {
    expect(formatBillions(500_000_000)).toBe("0.5");
  });
});

describe("formatMillions", () => {
  it("formats large numbers as millions with 1 decimal", () => {
    expect(formatMillions(57_300_000)).toBe("57.3");
  });

  it("formats exact millions", () => {
    expect(formatMillions(10_000_000)).toBe("10.0");
  });
});

describe("getChangeType", () => {
  it("returns increase for positive values", () => {
    expect(getChangeType(7.36)).toBe("increase");
    expect(getChangeType(0.01)).toBe("increase");
  });

  it("returns decrease for negative values", () => {
    expect(getChangeType(-2.1)).toBe("decrease");
    expect(getChangeType(-0.01)).toBe("decrease");
  });

  it("returns neutral for zero", () => {
    expect(getChangeType(0)).toBe("neutral");
  });
});

describe("formatPeriod", () => {
  it("formats YYYY-MM to full month name and year", () => {
    expect(formatPeriod("2026-02")).toBe("February 2026");
  });

  it("formats January", () => {
    expect(formatPeriod("2025-01")).toBe("January 2025");
  });

  it("formats December", () => {
    expect(formatPeriod("2025-12")).toBe("December 2025");
  });
});

describe("buildKPICard", () => {
  it("builds a complete KPI card for Square GPV", () => {
    const current = { value: 45_200_000_000, period: "2026-02" };
    const prior = { value: 42_100_000_000, period: "2025-02" };
    const card = buildKPICard("Square Global GPV", current, prior, "$B");

    expect(card.title).toBe("Square Global GPV (in billions)");
    expect(card.value).toBeCloseTo(45.2, 1);
    expect(card.unit).toBe("$B");
    expect(card.displayValue).toBe("45.2 $B");
    expect(card.change).toBeCloseTo(7.36, 1);
    expect(card.changeType).toBe("increase");
    expect(card.period).toBe("February 2026");
  });

  it("builds a KPI card with decrease", () => {
    const current = { value: 40_000_000_000, period: "2026-03" };
    const prior = { value: 42_000_000_000, period: "2025-03" };
    const card = buildKPICard("Square Global GPV", current, prior, "$B");

    expect(card.changeType).toBe("decrease");
    expect(card.change).toBeCloseTo(-4.76, 1);
  });

  it("builds a KPI card for actives in millions", () => {
    const current = { value: 57_300_000, period: "2026-02" };
    const prior = { value: 55_000_000, period: "2025-02" };
    const card = buildKPICard("Cash App Total Actives", current, prior, "M");

    expect(card.title).toBe("Cash App Total Actives");
    expect(card.value).toBeCloseTo(57.3, 1);
    expect(card.unit).toBe("M");
    expect(card.displayValue).toBe("57.3M");
  });
});

// --- Phase 2: Chart data transforms ---

// Realistic 25-month GP data (descending, ~$800M-$1B monthly)
const gpData25 = [
  { date: "2026-02-01", value: 921_890_158 },
  { date: "2026-01-01", value: 939_489_449 },
  { date: "2025-12-01", value: 1_045_280_199 },
  { date: "2025-11-01", value: 899_495_577 },
  { date: "2025-10-01", value: 927_449_600 },
  { date: "2025-09-01", value: 880_754_928 },
  { date: "2025-08-01", value: 890_051_644 },
  { date: "2025-07-01", value: 890_763_163 },
  { date: "2025-06-01", value: 837_765_457 },
  { date: "2025-05-01", value: 868_516_017 },
  { date: "2025-04-01", value: 830_249_069 },
  { date: "2025-03-01", value: 837_974_526 },
  { date: "2025-02-01", value: 721_408_009 },
  { date: "2025-01-01", value: 730_220_681 },
  { date: "2024-12-01", value: 786_530_466 },
  { date: "2024-11-01", value: 750_000_000 },
  { date: "2024-10-01", value: 770_000_000 },
  { date: "2024-09-01", value: 740_000_000 },
  { date: "2024-08-01", value: 760_000_000 },
  { date: "2024-07-01", value: 755_000_000 },
  { date: "2024-06-01", value: 710_000_000 },
  { date: "2024-05-01", value: 730_000_000 },
  { date: "2024-04-01", value: 700_000_000 },
  { date: "2024-03-01", value: 720_000_000 },
  { date: "2024-02-01", value: 650_000_000 },
];

const aoiData25 = [
  { date: "2026-02-01", value: 231_292_208 },
  { date: "2026-01-01", value: 177_196_400 },
  { date: "2025-12-01", value: 177_262_677 },
  { date: "2025-11-01", value: 205_308_991 },
  { date: "2025-10-01", value: 205_889_762 },
  { date: "2025-09-01", value: 80_927_824 },
  { date: "2025-08-01", value: 186_283_716 },
  { date: "2025-07-01", value: 212_958_876 },
  { date: "2025-06-01", value: 149_865_181 },
  { date: "2025-05-01", value: 200_160_021 },
  { date: "2025-04-01", value: 199_566_443 },
  { date: "2025-03-01", value: 208_707_352 },
  { date: "2025-02-01", value: 140_631_645 },
  { date: "2025-01-01", value: 116_929_766 },
  { date: "2024-12-01", value: 160_000_000 },
  { date: "2024-11-01", value: 145_000_000 },
  { date: "2024-10-01", value: 155_000_000 },
  { date: "2024-09-01", value: 130_000_000 },
  { date: "2024-08-01", value: 150_000_000 },
  { date: "2024-07-01", value: 148_000_000 },
  { date: "2024-06-01", value: 120_000_000 },
  { date: "2024-05-01", value: 140_000_000 },
  { date: "2024-04-01", value: 135_000_000 },
  { date: "2024-03-01", value: 130_000_000 },
  { date: "2024-02-01", value: 100_000_000 },
];

describe("calculateYoYSeries", () => {
  it("returns 13 months of YoY growth from 25 months of data", () => {
    const result = calculateYoYSeries(gpData25);
    expect(result.length).toBe(13);
    // Sorted ascending — last element is most recent
    expect(result[result.length - 1].month).toBe("Feb 2026");
    expect(result[0].month).toBe("Feb 2025");
  });

  it("calculates correct YoY percentage", () => {
    const result = calculateYoYSeries(gpData25);
    // Feb 2026: 921.9M vs Feb 2025: 721.4M → ~27.8%
    const feb = result.find((r) => r.month === "Feb 2026");
    expect(feb).toBeDefined();
    expect(feb!.yoy).toBeCloseTo(27.8, 0);
  });

  it("returns empty array for insufficient data", () => {
    expect(calculateYoYSeries([])).toEqual([]);
    expect(calculateYoYSeries([{ date: "2026-01-01", value: 100 }])).toEqual([]);
  });
});

describe("calculateRuleOf40", () => {
  it("returns combined GP YoY + Operating Margin for each month", () => {
    const result = calculateRuleOf40(gpData25, aoiData25);
    expect(result.length).toBeGreaterThan(0);
    expect(result[0]).toHaveProperty("gpYoY");
    expect(result[0]).toHaveProperty("opMargin");
    expect(result[0]).toHaveProperty("ruleOf40");
  });

  it("calculates Rule of 40 correctly", () => {
    const result = calculateRuleOf40(gpData25, aoiData25);
    // Rule of 40 = GP YoY Growth % + Operating Margin %
    const feb = result.find((r) => r.month === "Feb 2026");
    expect(feb).toBeDefined();
    // GP YoY ~27.8%, OpMargin = AOI/GP = 231M/922M = ~25.1%
    expect(feb!.ruleOf40).toBeCloseTo(feb!.gpYoY + feb!.opMargin, 1);
  });

  it("handles mismatched data lengths", () => {
    const shortAOI = aoiData25.slice(0, 15);
    const result = calculateRuleOf40(gpData25, shortAOI);
    // Should still work for months that have both GP and AOI
    expect(result.length).toBeGreaterThan(0);
  });
});

describe("calculateMarginSeries", () => {
  it("returns margin percentage for each month", () => {
    const result = calculateMarginSeries(aoiData25, gpData25);
    expect(result.length).toBeGreaterThan(0);
    expect(result[0]).toHaveProperty("aoi");
    expect(result[0]).toHaveProperty("margin");
  });

  it("calculates margin correctly", () => {
    const result = calculateMarginSeries(aoiData25, gpData25);
    const feb = result.find((r) => r.month === "Feb 2026");
    expect(feb).toBeDefined();
    // Margin = AOI/GP * 100 = 231M/922M * 100 = ~25.1%
    expect(feb!.margin).toBeCloseTo(25.1, 0);
  });

  it("handles zero GP without crashing", () => {
    const gpWithZero = [
      { date: "2026-01-01", value: 0 },
      { date: "2025-01-01", value: 100 },
    ];
    const aoiSmall = [{ date: "2026-01-01", value: 50 }];
    const result = calculateMarginSeries(aoiSmall, gpWithZero);
    // Should skip or handle the zero-GP month
    const jan = result.find((r) => r.month === "Jan 2026");
    if (jan) {
      expect(isFinite(jan.margin)).toBe(true);
    }
  });
});

describe("buildCumulativeWeeks", () => {
  // 2 weeks of daily data (Mon-Sun)
  // 2026-03-16 is a Monday
  const dailyData = [
    // Week 1: March 16-22 (Mon-Sun)
    { date: "2026-03-16", value: 1_000_000 },
    { date: "2026-03-17", value: 2_000_000 },
    { date: "2026-03-18", value: 1_500_000 },
    { date: "2026-03-19", value: 3_000_000 },
    { date: "2026-03-20", value: 2_500_000 },
    { date: "2026-03-21", value: 1_200_000 },
    { date: "2026-03-22", value: 800_000 },
    // Week 2: March 23-26 (Mon-Thu, partial)
    { date: "2026-03-23", value: 1_100_000 },
    { date: "2026-03-24", value: 2_200_000 },
    { date: "2026-03-25", value: 1_800_000 },
    { date: "2026-03-26", value: 2_900_000 },
  ];

  it("returns data grouped by day of week", () => {
    const result = buildCumulativeWeeks(dailyData);
    expect(result.length).toBe(7); // Mon-Sun
    expect(result[0].dayOfWeek).toBe("Mon");
    expect(result[6].dayOfWeek).toBe("Sun");
  });

  it("calculates cumulative sums correctly", () => {
    const result = buildCumulativeWeeks(dailyData);
    // Week 1: Mon=1M, Tue=1M+2M=3M, Wed=3M+1.5M=4.5M
    const mon = result[0];
    const tue = result[1];
    const wed = result[2];

    // Get the first week key
    const weekKeys = Object.keys(mon).filter((k) => k !== "dayOfWeek");
    const firstWeek = weekKeys[0];

    expect(mon[firstWeek]).toBe(1_000_000);
    expect(tue[firstWeek]).toBe(3_000_000);
    expect(wed[firstWeek]).toBe(4_500_000);
  });

  it("handles empty input", () => {
    expect(buildCumulativeWeeks([])).toEqual([]);
  });
});
