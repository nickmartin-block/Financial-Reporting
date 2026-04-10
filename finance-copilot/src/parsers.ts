import type { StatusCardData, SummaryCardData, StockData, NewsItem } from "./types";

const MONTH_NAMES: Record<string, number> = {
  january: 0, february: 1, march: 2, april: 3, may: 4, june: 5,
  july: 6, august: 7, september: 8, october: 9, november: 10, december: 11,
};

/**
 * Parse a digest tab title like "Week of March 21, 2026" into a Date.
 * Returns null if the title doesn't match the expected pattern.
 */
export function parseDigestTabTitle(title: string): Date | null {
  const match = title.match(/week\s+of\s+(\w+)\s+(\d+),?\s*(\d{4})/i);
  if (!match) return null;
  const monthIdx = MONTH_NAMES[match[1].toLowerCase()];
  if (monthIdx === undefined) return null;
  const day = parseInt(match[2], 10);
  const year = parseInt(match[3], 10);
  return new Date(Date.UTC(year, monthIdx, day));
}

/**
 * Sort tabs by their parsed title date, newest first.
 * Filters out tabs whose titles can't be parsed as dates.
 */
export function sortTabsByDate(
  tabs: Array<{ tabProperties: { title: string } }>
): Array<{ tabProperties: { title: string } }> {
  return tabs
    .filter((tab) => parseDigestTabTitle(tab.tabProperties.title) !== null)
    .sort((a, b) => {
      const da = parseDigestTabTitle(a.tabProperties.title)!.getTime();
      const db = parseDigestTabTitle(b.tabProperties.title)!.getTime();
      return db - da;
    });
}

/**
 * Extract concatenated text from a Google Docs body.content array.
 * Walks paragraph → elements → textRun.content.
 */
export function extractTabText(bodyContent: any[]): string {
  if (!bodyContent || !Array.isArray(bodyContent)) return "";
  const paragraphs: string[] = [];
  for (const block of bodyContent) {
    if (!block.paragraph || !block.paragraph.elements) continue;
    const parts: string[] = [];
    for (const el of block.paragraph.elements) {
      if (el.textRun && el.textRun.content) {
        parts.push(el.textRun.content);
      }
    }
    if (parts.length > 0) {
      paragraphs.push(parts.join("").replace(/\n$/, ""));
    }
  }
  return paragraphs.join("\n");
}

/**
 * Build a StatusCardData from two weeks of digest text.
 * Uses keyword matching to detect GP trends and determine status.
 */
export function buildDigestStatus(
  currentWeekTitle: string,
  currentText: string,
  priorText: string
): StatusCardData {
  const date = parseDigestTabTitle(currentWeekTitle);
  const timestamp = date ? date.toISOString().slice(0, 10) : new Date().toISOString().slice(0, 10);

  // Extract dollar amounts from text (e.g., "$2.5B")
  const extractAmount = (text: string): number | null => {
    const match = text.match(/(?:Block\s+)?GP[:\s]+\$?([\d.]+)B/i);
    if (!match) return null;
    return parseFloat(match[1]);
  };

  // Check for YoY percentage
  const extractYoY = (text: string): number | null => {
    const match = text.match(/([+-]?\d+(?:\.\d+)?)\s*%\s*YoY/i);
    if (!match) return null;
    return parseFloat(match[1]);
  };

  // Check for outlook comparison
  const isAboveOutlook = (text: string): boolean | null => {
    if (/above\s+outlook/i.test(text)) return true;
    if (/below\s+outlook/i.test(text)) return false;
    return null;
  };

  const currentGP = extractAmount(currentText);
  const priorGP = extractAmount(priorText);
  const currentYoY = extractYoY(currentText);
  const outlook = isAboveOutlook(currentText);

  let status: StatusCardData["status"] = "info";
  let summary: string;

  if (currentGP !== null && priorGP !== null) {
    if (currentGP >= priorGP) {
      status = "success";
      summary = `Block GP rose to $${currentGP}B from $${priorGP}B week-over-week.`;
    } else if (outlook === true) {
      status = "warning";
      summary = `Block GP declined to $${currentGP}B from $${priorGP}B but remains above Outlook.`;
    } else if (outlook === false) {
      status = "error";
      summary = `Block GP declined to $${currentGP}B from $${priorGP}B and is below Outlook.`;
    } else {
      status = "warning";
      summary = `Block GP declined to $${currentGP}B from $${priorGP}B week-over-week.`;
    }
    if (currentYoY !== null) {
      summary += ` YoY growth: ${currentYoY > 0 ? "+" : ""}${currentYoY}%.`;
    }
  } else {
    summary = "Weekly digest available. Review for latest Block performance metrics.";
  }

  return {
    title: "Block Performance Digest Update",
    summary,
    status,
    timestamp,
  };
}

/**
 * Extract strategic priorities and DRIs from a Google Slides API response.
 */
export function parseSlidesContent(
  presentation: any,
  sourceUrl: string
): SummaryCardData {
  const details: Array<{ area: string; description: string; dri: string }> = [];
  const allText: string[] = [];

  if (presentation.slides && Array.isArray(presentation.slides)) {
    for (const slide of presentation.slides) {
      if (!slide.pageElements) continue;
      for (const element of slide.pageElements) {
        if (!element.shape || !element.shape.text || !element.shape.text.textElements) continue;
        for (const textEl of element.shape.text.textElements) {
          if (!textEl.textRun || !textEl.textRun.content) continue;
          const line = textEl.textRun.content.trim();
          if (!line) continue;
          allText.push(line);

          // Look for "Priority: X — DRI: Name" or "Area — DRI: Name"
          const driMatch = line.match(/(?:Priority\s*\d*:\s*)?(.+?)(?:\s*[-—]\s*DRI:\s*(.+))/i);
          if (driMatch) {
            details.push({
              area: driMatch[1].trim(),
              description: driMatch[1].trim(),
              dri: driMatch[2].trim(),
            });
          }
        }
      }
    }
  }

  const count = details.length;
  const summary = count > 0
    ? `${count} strategic priorities identified across key focus areas.`
    : "No priorities extracted from presentation.";

  return {
    title: presentation.title || "Guidance Team Goals",
    summary,
    details,
    sourceUrl,
  };
}

/**
 * Parse Yahoo Finance chart API response into StockData.
 */
export function parseStockResponse(yahooData: any): StockData | null {
  try {
    const result = yahooData?.chart?.result?.[0];
    if (!result) return null;

    const meta = result.meta;
    if (!meta || !meta.regularMarketPrice) return null;

    const price = meta.regularMarketPrice;
    const previousClose = meta.previousClose || price;
    const change = price - previousClose;
    const changePercent = previousClose > 0 ? (change / previousClose) * 100 : 0;

    const closes: number[] = result.indicators?.quote?.[0]?.close || [];
    const sparkline = closes.filter((v: any) => v !== null && v !== undefined && typeof v === "number");

    return {
      symbol: meta.symbol || "XYZ",
      price,
      change,
      changePercent,
      previousClose,
      timestamp: meta.regularMarketTime || Math.floor(Date.now() / 1000),
      sparkline,
    };
  } catch {
    return null;
  }
}

/**
 * Parse Google News RSS XML into an array of NewsItems.
 * Uses regex since Workers don't have DOMParser.
 */
export function parseNewsRSS(xml: string): NewsItem[] {
  if (!xml || typeof xml !== "string") return [];

  const items: NewsItem[] = [];
  const itemRegex = /<item>([\s\S]*?)<\/item>/g;
  let match;

  while ((match = itemRegex.exec(xml)) !== null) {
    const block = match[1];

    const titleMatch = block.match(/<title>([\s\S]*?)<\/title>/);
    const linkMatch = block.match(/<link>([\s\S]*?)<\/link>/);
    const sourceMatch = block.match(/<source[^>]*>([\s\S]*?)<\/source>/);
    const pubDateMatch = block.match(/<pubDate>([\s\S]*?)<\/pubDate>/);

    if (titleMatch) {
      items.push({
        title: titleMatch[1].trim(),
        url: linkMatch ? linkMatch[1].trim() : "",
        source: sourceMatch ? sourceMatch[1].trim() : "Unknown",
        publishedAt: pubDateMatch ? new Date(pubDateMatch[1].trim()).toISOString() : new Date().toISOString(),
      });
    }
  }

  // Sort by date descending
  items.sort((a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime());

  // Max 8 items
  return items.slice(0, 8);
}
