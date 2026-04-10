import { Hono } from "hono";
import { serveStatic } from "hono/cloudflare-workers";
import type { Env } from "./types";
import { parseStockResponse, parseNewsRSS } from "./parsers";

const app = new Hono<{ Bindings: Env }>();

const CACHE_TTL_SEC = 7 * 24 * 60 * 60; // 7 days
const STOCK_TTL_SEC = 15 * 60; // 15 minutes
const NEWS_TTL_SEC = 60 * 60; // 1 hour

async function ensureTable(db: D1Database) {
  await db.prepare(
    "CREATE TABLE IF NOT EXISTS query_cache (cache_key TEXT PRIMARY KEY, data TEXT NOT NULL, created_at INTEGER NOT NULL)"
  ).run();
}

async function getCachedOrFetch<T>(
  db: D1Database,
  key: string,
  ttlSec: number,
  fetchFn: () => Promise<T>
): Promise<T | null> {
  await ensureTable(db);
  const row = await db.prepare(
    "SELECT data, created_at FROM query_cache WHERE cache_key = ?"
  ).bind(key).first<{ data: string; created_at: number }>();

  if (row) {
    const age = Math.floor(Date.now() / 1000) - row.created_at;
    if (age <= ttlSec) {
      return JSON.parse(row.data) as T;
    }
    await db.prepare("DELETE FROM query_cache WHERE cache_key = ?").bind(key).run();
  }

  const data = await fetchFn();
  if (data) {
    await db.prepare(
      "INSERT OR REPLACE INTO query_cache (cache_key, data, created_at) VALUES (?, ?, ?)"
    ).bind(key, JSON.stringify(data), Math.floor(Date.now() / 1000)).run();
  }
  return data;
}

app.get("/api/health", (c) => {
  return c.json({ status: "ok", app: "finance-copilot" });
});

app.get("/api/cache", async (c) => {
  const key = c.req.query("key");
  if (!key) return c.json({ error: "key required" }, 400);

  await ensureTable(c.env.DB);
  const row = await c.env.DB.prepare(
    "SELECT data, created_at FROM query_cache WHERE cache_key = ?"
  ).bind(key).first<{ data: string; created_at: number }>();

  if (!row) return c.json({ hit: false }, 404);

  const age = Math.floor(Date.now() / 1000) - row.created_at;
  if (age > CACHE_TTL_SEC) {
    await c.env.DB.prepare("DELETE FROM query_cache WHERE cache_key = ?").bind(key).run();
    return c.json({ hit: false }, 404);
  }

  return c.json({ hit: true, data: JSON.parse(row.data), age });
});

app.post("/api/cache", async (c) => {
  const body = await c.req.json<{ key?: string; data?: unknown }>();
  if (!body.key || !body.data) return c.json({ error: "key and data required" }, 400);

  await ensureTable(c.env.DB);
  await c.env.DB.prepare(
    "INSERT OR REPLACE INTO query_cache (cache_key, data, created_at) VALUES (?, ?, ?)"
  ).bind(body.key, JSON.stringify(body.data), Math.floor(Date.now() / 1000)).run();

  return c.json({ stored: true });
});

app.get("/api/stock", async (c) => {
  try {
    const data = await getCachedOrFetch(c.env.DB, "finance-copilot-stock-v2", STOCK_TTL_SEC, async () => {
      // Try Yahoo Finance v8 chart API
      const urls = [
        "https://query2.finance.yahoo.com/v8/finance/chart/XYZ?range=1mo&interval=1d",
        "https://query1.finance.yahoo.com/v8/finance/chart/XYZ?range=1mo&interval=1d",
      ];
      for (const url of urls) {
        try {
          const res = await fetch(url, {
            headers: { "User-Agent": "Mozilla/5.0", "Accept": "application/json" },
          });
          if (res.ok) {
            const json = await res.json() as any;
            const parsed = parseStockResponse(json);
            if (parsed) return parsed;
          }
        } catch { /* try next URL */ }
      }
      throw new Error("All stock API endpoints failed");
    });
    if (!data) return c.json({ error: "Failed to parse stock data" }, 502);
    return c.json(data);
  } catch (e: any) {
    return c.json({ error: e.message || "Stock fetch failed" }, 502);
  }
});

app.get("/api/news", async (c) => {
  try {
    const data = await getCachedOrFetch(c.env.DB, "finance-copilot-news-v3", NEWS_TTL_SEC, async () => {
      const res = await fetch(
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=XYZ&region=US&lang=en-US",
        { headers: { "User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml, application/xml, text/xml" } }
      );
      if (!res.ok) throw new Error("Yahoo Finance News HTTP " + res.status);
      const xml = await res.text();
      const items = parseNewsRSS(xml);
      return { items, fetchedAt: new Date().toISOString() };
    });
    if (!data) return c.json({ error: "Failed to parse news data" }, 502);
    return c.json(data);
  } catch (e: any) {
    return c.json({ error: e.message || "News fetch failed" }, 502);
  }
});

app.get("/*", serveStatic({ root: "./" }));

export default app;
