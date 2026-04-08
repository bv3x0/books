/**
 * Semantic search API endpoint.
 *
 * Searches claim embeddings in Neon Postgres using pgvector.
 * Query is embedded via OpenAI, then cosine similarity finds matches.
 *
 * Usage:
 *     GET /api/search?q=your+query
 *     GET /api/search?q=your+query&limit=20
 *     GET /api/search?q=your+query&book=american-nations
 */

const { neon } = require('@neondatabase/serverless');
const OpenAI = require('openai').default;

const MAX_QUERY_LENGTH = 1000;

// Lazy-initialized clients
let sql;
let openai;
let claimsSchemaPromise;

function getPostgresUrl() {
  return (
    process.env.POSTGRES_URL ||
    process.env.POSTGRES_URL_NON_POOLING ||
    process.env.DATABASE_URL_UNPOOLED
  );
}

function getClients() {
  if (!sql) {
    const postgresUrl = getPostgresUrl();
    if (!postgresUrl) {
      throw new Error('Postgres environment variable is not set');
    }
    sql = neon(postgresUrl);
  }
  if (!openai) {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      throw new Error('OpenAI API key not configured');
    }
    openai = new OpenAI({ apiKey });
  }
  return { sql, openai };
}

async function getClaimsSchema() {
  if (!claimsSchemaPromise) {
    const { sql } = getClients();
    claimsSchemaPromise = sql`
      SELECT column_name
      FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'claims'
    `.then(rows => new Set(rows.map(row => row.column_name)));
  }
  return claimsSchemaPromise;
}

// Rate limiting
const RATE_LIMIT_REQUESTS = 10;
const RATE_LIMIT_WINDOW = 60 * 1000;
const rateLimitStore = new Map();

function checkRateLimit(clientIp) {
  const now = Date.now();
  const windowStart = now - RATE_LIMIT_WINDOW;
  let timestamps = rateLimitStore.get(clientIp) || [];
  timestamps = timestamps.filter(ts => ts > windowStart);

  if (timestamps.length >= RATE_LIMIT_REQUESTS) {
    return { allowed: false, remaining: 0 };
  }

  timestamps.push(now);
  rateLimitStore.set(clientIp, timestamps);
  return { allowed: true, remaining: RATE_LIMIT_REQUESTS - timestamps.length };
}

function getClientIp(req) {
  const forwarded = req.headers['x-forwarded-for'];
  if (forwarded) {
    return forwarded.split(',')[0].trim();
  }
  return req.headers['x-real-ip'] || 'unknown';
}

async function getEmbedding(text) {
  const { openai } = getClients();
  const response = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text,
  });
  return response.data[0].embedding;
}

function safeParseJson(value, fallback) {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  if (typeof value === 'object') {
    return value;
  }
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function parseTextList(value) {
  if (!value) {
    return [];
  }
  if (Array.isArray(value)) {
    return value.map(v => String(v).trim()).filter(Boolean);
  }
  return String(value)
    .split(',')
    .map(v => v.trim())
    .filter(Boolean);
}

function normalizeEntities(row) {
  const structured = safeParseJson(row.entities_json, null);
  if (structured && typeof structured === 'object' && !Array.isArray(structured)) {
    return {
      people: Array.isArray(structured.people) ? structured.people : [],
      places: Array.isArray(structured.places) ? structured.places : [],
      events: Array.isArray(structured.events) ? structured.events : [],
      works: Array.isArray(structured.works) ? structured.works : [],
    };
  }

  const flat = parseTextList(row.entities);
  return { people: [], places: [], events: [], works: [], flat };
}

async function searchClaims(queryEmbedding, limit = 10, bookFilter = null) {
  const { sql } = getClients();
  const vectorLiteral = `[${queryEmbedding.join(',')}]`;
  const schema = await getClaimsSchema();
  const richMetadataAvailable = [
    'concepts_json',
    'entities',
    'entities_json',
    'sub_points_json',
    'embedding_text',
  ].every(col => schema.has(col));

  let results;
  if (richMetadataAvailable) {
    if (bookFilter) {
      results = await sql`
        SELECT id, book_name, chapter, text, embedding_text,
               concepts, concepts_json, entities, entities_json, sub_points_json,
               1 - (embedding <=> ${vectorLiteral}::vector) as similarity
        FROM claims
        WHERE book_name = ${bookFilter}
        ORDER BY embedding <=> ${vectorLiteral}::vector
        LIMIT ${limit}
      `;
    } else {
      results = await sql`
        SELECT id, book_name, chapter, text, embedding_text,
               concepts, concepts_json, entities, entities_json, sub_points_json,
               1 - (embedding <=> ${vectorLiteral}::vector) as similarity
        FROM claims
        ORDER BY embedding <=> ${vectorLiteral}::vector
        LIMIT ${limit}
      `;
    }
  } else {
    if (bookFilter) {
      results = await sql`
        SELECT id, book_name, chapter, text, concepts,
               1 - (embedding <=> ${vectorLiteral}::vector) as similarity
        FROM claims
        WHERE book_name = ${bookFilter}
        ORDER BY embedding <=> ${vectorLiteral}::vector
        LIMIT ${limit}
      `;
    } else {
      results = await sql`
        SELECT id, book_name, chapter, text, concepts,
               1 - (embedding <=> ${vectorLiteral}::vector) as similarity
        FROM claims
        ORDER BY embedding <=> ${vectorLiteral}::vector
        LIMIT ${limit}
      `;
    }
  }

  return results.map(row => ({
    id: row.id,
    book: row.book_name,
    chapter: row.chapter || '',
    text: row.text,
    embedding_text: row.embedding_text || row.text,
    concepts: safeParseJson(row.concepts_json, parseTextList(row.concepts)),
    entities: normalizeEntities(row),
    sub_points: safeParseJson(row.sub_points_json, []),
    score: Math.round(row.similarity * 10000) / 10000,
  }));
}

module.exports = async function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  // Only allow GET
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Check rate limit
  const clientIp = getClientIp(req);
  const { allowed } = checkRateLimit(clientIp);

  if (!allowed) {
    res.setHeader('Retry-After', '60');
    return res.status(429).json({
      error: 'Rate limit exceeded. Please wait a minute before searching again.'
    });
  }

  // Parse query parameters
  const query = String(req.query.q || '').trim();
  const requestedLimit = parseInt(req.query.limit || '10', 10);
  const limit = Number.isFinite(requestedLimit)
    ? Math.min(Math.max(requestedLimit, 1), 50)
    : 10;
  const book = req.query.book ? String(req.query.book).trim() : null;

  // Validate required query parameter
  if (!query) {
    return res.status(400).json({ error: "Missing required 'q' parameter" });
  }
  if (query.length > MAX_QUERY_LENGTH) {
    return res.status(400).json({ error: 'Query is too long' });
  }

  try {
    // Generate embedding for query
    const queryEmbedding = await getEmbedding(query);

    // Search for similar claims
    const results = await searchClaims(queryEmbedding, limit, book);

    // Return results
    res.setHeader('Cache-Control', 'public, max-age=60');
    return res.status(200).json({
      query,
      count: results.length,
      results,
    });
  } catch (error) {
    console.error('Search error:', error);
    return res.status(500).json({ error: 'Search failed' });
  }
};
