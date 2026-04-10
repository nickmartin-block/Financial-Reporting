import { describe, it, expect } from "vitest";
import {
  parseDigestTabTitle,
  sortTabsByDate,
  extractTabText,
  buildDigestStatus,
  parseSlidesContent,
  parseStockResponse,
  parseNewsRSS,
} from "../src/parsers";

// --- Mock data ---

const mockDocsTab = (title: string, text: string) => ({
  tabProperties: { title },
  body: {
    content: [
      {
        paragraph: {
          elements: [{ textRun: { content: text } }],
        },
      },
    ],
  },
});

const mockYahooFinance = {
  chart: {
    result: [
      {
        meta: {
          symbol: "XYZ",
          regularMarketPrice: 87.45,
          previousClose: 85.20,
          regularMarketTime: 1711641600,
        },
        indicators: {
          quote: [
            {
              close: [82.1, 83.5, null, 84.2, 85.0, 85.2, 86.1, 87.0, 87.45],
            },
          ],
        },
      },
    ],
  },
};

const mockRSS = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Block Inc News</title>
    <item>
      <title>Block Reports Strong Q4 Earnings</title>
      <link>https://example.com/article1</link>
      <source url="https://reuters.com">Reuters</source>
      <pubDate>Fri, 28 Mar 2026 14:00:00 GMT</pubDate>
    </item>
    <item>
      <title>XYZ Stock Rises on Revenue Beat</title>
      <link>https://example.com/article2</link>
      <source url="https://bloomberg.com">Bloomberg</source>
      <pubDate>Thu, 27 Mar 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Square Expands International Presence</title>
      <link>https://example.com/article3</link>
      <source url="https://cnbc.com">CNBC</source>
      <pubDate>Wed, 26 Mar 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>`;

// --- Tests ---

describe("parseDigestTabTitle", () => {
  it("extracts date from 'Week of March 21, 2026'", () => {
    const result = parseDigestTabTitle("Week of March 21, 2026");
    expect(result).toBeInstanceOf(Date);
    expect(result!.getUTCFullYear()).toBe(2026);
    expect(result!.getUTCMonth()).toBe(2); // March = 2
    expect(result!.getUTCDate()).toBe(21);
  });

  it("extracts date from 'Week of March 21 2026' (no comma)", () => {
    const result = parseDigestTabTitle("Week of March 21 2026");
    expect(result).toBeInstanceOf(Date);
    expect(result!.getUTCFullYear()).toBe(2026);
    expect(result!.getUTCDate()).toBe(21);
  });

  it("returns null for non-date titles like 'Overview'", () => {
    expect(parseDigestTabTitle("Overview")).toBeNull();
    expect(parseDigestTabTitle("Template")).toBeNull();
  });
});

describe("sortTabsByDate", () => {
  it("sorts tabs newest-first by parsed title date", () => {
    const tabs = [
      { tabProperties: { title: "Week of March 7, 2026" } },
      { tabProperties: { title: "Week of March 21, 2026" } },
      { tabProperties: { title: "Week of March 14, 2026" } },
    ];
    const sorted = sortTabsByDate(tabs);
    expect(sorted[0].tabProperties.title).toBe("Week of March 21, 2026");
    expect(sorted[1].tabProperties.title).toBe("Week of March 14, 2026");
    expect(sorted[2].tabProperties.title).toBe("Week of March 7, 2026");
  });

  it("filters out tabs without parseable dates", () => {
    const tabs = [
      { tabProperties: { title: "Overview" } },
      { tabProperties: { title: "Week of March 21, 2026" } },
    ];
    const sorted = sortTabsByDate(tabs);
    expect(sorted.length).toBe(1);
    expect(sorted[0].tabProperties.title).toBe("Week of March 21, 2026");
  });
});

describe("extractTabText", () => {
  it("concatenates paragraph text from body content", () => {
    const content = [
      { paragraph: { elements: [{ textRun: { content: "Hello " } }, { textRun: { content: "world" } }] } },
      { paragraph: { elements: [{ textRun: { content: "Second paragraph" } }] } },
    ];
    expect(extractTabText(content)).toBe("Hello world\nSecond paragraph");
  });

  it("returns empty string for empty or null body content", () => {
    expect(extractTabText([])).toBe("");
    expect(extractTabText(null as any)).toBe("");
  });

  it("skips elements without textRun", () => {
    const content = [
      { paragraph: { elements: [{ textRun: { content: "Text" } }, { inlineObjectElement: {} }] } },
    ];
    expect(extractTabText(content)).toBe("Text");
  });
});

describe("buildDigestStatus", () => {
  it("returns 'success' when GP text shows improvement", () => {
    const current = "Block GP: $2.5B (+8% YoY). Performance above Outlook by 3%. Cash App GP strong.";
    const prior = "Block GP: $2.3B (+6% YoY). Performance above Outlook by 1%.";
    const result = buildDigestStatus("Week of March 21, 2026", current, prior);
    expect(result.status).toBe("success");
    expect(result.title).toBe("Block Performance Digest Update");
  });

  it("returns 'warning' when GP declined", () => {
    const current = "Block GP: $2.1B (-2% YoY). Performance above Outlook.";
    const prior = "Block GP: $2.3B (+6% YoY). Performance above Outlook.";
    const result = buildDigestStatus("Week of March 21, 2026", current, prior);
    expect(result.status).toBe("warning");
  });

  it("returns 'info' when insufficient data for comparison", () => {
    const result = buildDigestStatus("Week of March 21, 2026", "No metrics available", "No metrics available");
    expect(result.status).toBe("info");
  });

  it("generates summary under 40 words", () => {
    const current = "Block GP: $2.5B (+8% YoY). Performance above Outlook by 3%.";
    const prior = "Block GP: $2.3B (+6% YoY). Performance above Outlook by 1%.";
    const result = buildDigestStatus("Week of March 21, 2026", current, prior);
    const wordCount = result.summary.split(/\s+/).length;
    expect(wordCount).toBeLessThanOrEqual(40);
  });

  it("extracts timestamp from current week title", () => {
    const result = buildDigestStatus(
      "Week of March 21, 2026",
      "Block GP: $2.5B (+8% YoY).",
      "Block GP: $2.3B (+6% YoY)."
    );
    expect(result.timestamp).toContain("2026");
  });
});

describe("parseSlidesContent", () => {
  it("extracts priority text from slide shape elements", () => {
    const presentation = {
      title: "Block Guidance Team 2025 Goals",
      slides: [
        {
          pageElements: [
            {
              shape: {
                text: {
                  textElements: [
                    { textRun: { content: "Strategic Focus Areas\n" } },
                    { textRun: { content: "Revenue Growth — DRI: Alice Smith\n" } },
                    { textRun: { content: "Cost Efficiency — DRI: Bob Jones\n" } },
                  ],
                },
              },
            },
          ],
        },
      ],
    };
    const result = parseSlidesContent(presentation, "https://slides.example.com");
    expect(result.details.length).toBeGreaterThan(0);
    expect(result.sourceUrl).toBe("https://slides.example.com");
  });

  it("extracts DRI names from 'DRI: Name' patterns", () => {
    const presentation = {
      title: "Goals",
      slides: [
        {
          pageElements: [
            {
              shape: {
                text: {
                  textElements: [
                    { textRun: { content: "Priority 1: Revenue Growth — DRI: Alice Smith\n" } },
                  ],
                },
              },
            },
          ],
        },
      ],
    };
    const result = parseSlidesContent(presentation, "https://example.com");
    const withDRI = result.details.find((d) => d.dri !== "");
    expect(withDRI).toBeDefined();
    expect(withDRI!.dri).toBe("Alice Smith");
  });

  it("generates summary under 20 words", () => {
    const presentation = {
      title: "Block Guidance Team 2025 Goals",
      slides: [
        {
          pageElements: [
            {
              shape: {
                text: {
                  textElements: [
                    { textRun: { content: "Priority: Revenue\n" } },
                    { textRun: { content: "Priority: Efficiency\n" } },
                  ],
                },
              },
            },
          ],
        },
      ],
    };
    const result = parseSlidesContent(presentation, "https://example.com");
    const wordCount = result.summary.split(/\s+/).length;
    expect(wordCount).toBeLessThanOrEqual(20);
  });

  it("returns empty details for presentation with no matching content", () => {
    const presentation = { title: "Empty", slides: [] };
    const result = parseSlidesContent(presentation, "https://example.com");
    expect(result.details).toEqual([]);
  });
});

describe("parseStockResponse", () => {
  it("extracts price from Yahoo Finance chart response", () => {
    const result = parseStockResponse(mockYahooFinance);
    expect(result).not.toBeNull();
    expect(result!.symbol).toBe("XYZ");
    expect(result!.price).toBe(87.45);
  });

  it("calculates correct change and changePercent", () => {
    const result = parseStockResponse(mockYahooFinance)!;
    expect(result.change).toBeCloseTo(2.25, 1);
    expect(result.changePercent).toBeCloseTo(2.64, 1);
    expect(result.previousClose).toBe(85.20);
  });

  it("builds sparkline array from close prices", () => {
    const result = parseStockResponse(mockYahooFinance)!;
    expect(result.sparkline.length).toBeGreaterThan(0);
    expect(result.sparkline.every((v) => typeof v === "number")).toBe(true);
  });

  it("filters null values from sparkline", () => {
    const result = parseStockResponse(mockYahooFinance)!;
    expect(result.sparkline.includes(null as any)).toBe(false);
    // Original data has 9 entries, one null → sparkline should have 8
    expect(result.sparkline.length).toBe(8);
  });

  it("returns null for malformed response", () => {
    expect(parseStockResponse({})).toBeNull();
    expect(parseStockResponse({ chart: {} })).toBeNull();
    expect(parseStockResponse({ chart: { result: [] } })).toBeNull();
  });
});

describe("parseNewsRSS", () => {
  it("extracts title, source, url, publishedAt from items", () => {
    const items = parseNewsRSS(mockRSS);
    expect(items.length).toBe(3);
    expect(items[0].title).toBe("Block Reports Strong Q4 Earnings");
    expect(items[0].source).toBe("Reuters");
    expect(items[0].url).toBe("https://example.com/article1");
    expect(items[0].publishedAt).toContain("2026");
  });

  it("returns max 8 items", () => {
    // Build RSS with 12 items
    let items = "";
    for (let i = 0; i < 12; i++) {
      items += `<item><title>Article ${i}</title><link>https://example.com/${i}</link><source>Src</source><pubDate>Fri, ${10 + i} Mar 2026 10:00:00 GMT</pubDate></item>`;
    }
    const bigRSS = `<rss><channel>${items}</channel></rss>`;
    const result = parseNewsRSS(bigRSS);
    expect(result.length).toBeLessThanOrEqual(8);
  });

  it("sorts by date descending (newest first)", () => {
    const items = parseNewsRSS(mockRSS);
    expect(items[0].title).toBe("Block Reports Strong Q4 Earnings"); // March 28
    expect(items[2].title).toBe("Square Expands International Presence"); // March 26
  });

  it("returns empty array for invalid XML", () => {
    expect(parseNewsRSS("")).toEqual([]);
    expect(parseNewsRSS("not xml")).toEqual([]);
    expect(parseNewsRSS("<rss><channel></channel></rss>")).toEqual([]);
  });
});
