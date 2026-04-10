export interface MetricValue {
  value: number;
  period: string;
}

export interface KPICardData {
  title: string;
  value: number;
  unit: string;
  displayValue: string;
  change: number;
  changeType: "increase" | "decrease" | "neutral";
  period: string;
}

export interface CacheEntry {
  cache_key: string;
  data: string;
  created_at: number;
}

export interface TimeSeriesPoint {
  date: string;
  value: number;
}

export interface YoYPoint {
  month: string;
  yoy: number;
}

export interface RuleOf40Point {
  month: string;
  gpYoY: number;
  opMargin: number;
  ruleOf40: number;
}

export interface MarginPoint {
  month: string;
  aoi: number;
  margin: number;
}

export interface CumulativeWeekData {
  dayOfWeek: string;
  [weekLabel: string]: number | string;
}

export interface StatusCardData {
  title: string;
  summary: string;
  status: "success" | "warning" | "error" | "info";
  timestamp: string;
}

export interface SummaryDetail {
  area: string;
  description: string;
  dri: string;
}

export interface SummaryCardData {
  title: string;
  summary: string;
  details: SummaryDetail[];
  sourceUrl: string;
}

export interface StockData {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  previousClose: number;
  timestamp: number;
  sparkline: number[];
}

export interface NewsItem {
  title: string;
  source: string;
  url: string;
  publishedAt: string;
}

export interface NewsData {
  items: NewsItem[];
  fetchedAt: string;
}

export interface Env {
  DB: D1Database;
}
