import { describe, it, expect, beforeEach } from "vitest";
import { env } from "cloudflare:test";
import app from "../src/server";

describe("GET /api/health", () => {
  it("returns health status", async () => {
    const res = await app.request("/api/health");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ status: "ok", app: "finance-copilot" });
  });
});

describe("GET /api/cache", () => {
  it("returns 400 when key is missing", async () => {
    const res = await app.request("/api/cache", {}, env);
    expect(res.status).toBe(400);
  });

  it("returns cache miss for unknown key", async () => {
    const res = await app.request("/api/cache?key=nonexistent", {}, env);
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.hit).toBe(false);
  });
});

describe("POST /api/cache", () => {
  it("returns 400 when key or data is missing", async () => {
    const res = await app.request("/api/cache", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "test" }),
    }, env);
    expect(res.status).toBe(400);
  });

  it("stores data successfully", async () => {
    const res = await app.request("/api/cache", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        key: "test-key",
        data: { metric: "square_gpv", value: 45_200_000_000 },
      }),
    }, env);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.stored).toBe(true);
  });
});

describe("cache roundtrip", () => {
  it("stores and retrieves cached data", async () => {
    const data = { gpv: 45_200_000_000, period: "2026-02" };

    await app.request("/api/cache", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "square-gpv-latest", data }),
    }, env);

    const res = await app.request("/api/cache?key=square-gpv-latest", {}, env);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.hit).toBe(true);
    expect(body.data.gpv).toBe(45_200_000_000);
    expect(body.data.period).toBe("2026-02");
    expect(typeof body.age).toBe("number");
  });
});

describe("GET /api/stock", () => {
  it("returns stock data JSON with correct shape", async () => {
    const res = await app.request("/api/stock", {}, env);
    // May return 200 (with data or cached) or 502 (upstream failure)
    // In test env, upstream will fail, so we accept 502
    expect([200, 502]).toContain(res.status);
    if (res.status === 200) {
      const body = await res.json();
      expect(body).toHaveProperty("symbol");
      expect(body).toHaveProperty("price");
      expect(body).toHaveProperty("sparkline");
    }
  });

  it("returns valid response shape", async () => {
    const res = await app.request("/api/stock", {}, env);
    const body = await res.json();
    if (res.status === 200) {
      expect(body).toHaveProperty("symbol");
      expect(body).toHaveProperty("price");
      expect(typeof body.price).toBe("number");
    } else {
      expect(body).toHaveProperty("error");
    }
  });
});

describe("GET /api/news", () => {
  it("returns news data JSON or 502", async () => {
    const res = await app.request("/api/news", {}, env);
    expect([200, 502]).toContain(res.status);
    if (res.status === 200) {
      const body = await res.json();
      expect(body).toHaveProperty("items");
      expect(body).toHaveProperty("fetchedAt");
    }
  });

  it("returns valid response shape", async () => {
    const res = await app.request("/api/news", {}, env);
    const body = await res.json();
    if (res.status === 200) {
      expect(Array.isArray(body.items)).toBe(true);
      expect(typeof body.fetchedAt).toBe("string");
    } else {
      expect(body).toHaveProperty("error");
    }
  });
});

describe("cache TTL", () => {
  it("expires cached data after TTL", async () => {
    // Directly insert with old timestamp (8 days ago)
    await env.DB.prepare(
      "CREATE TABLE IF NOT EXISTS query_cache (cache_key TEXT PRIMARY KEY, data TEXT NOT NULL, created_at INTEGER NOT NULL)"
    ).run();
    const oldTimestamp = Math.floor(Date.now() / 1000) - 700_000;
    await env.DB.prepare(
      "INSERT INTO query_cache (cache_key, data, created_at) VALUES (?, ?, ?)"
    ).bind("old-key", '{"test":true}', oldTimestamp).run();

    const res = await app.request("/api/cache?key=old-key", {}, env);
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.hit).toBe(false);
  });
});
