#!/usr/bin/env node
// Model-routing gateway for Claude Code.
//   model starts with "claude-"  -> Anthropic, byte-for-byte pass-through (claude.ai login stays active)
//   anything else                -> Ollama (/v1/messages), body stripped of fields Ollama rejects
// Zero dependencies. Node >= 18.

import http from 'node:http';
import https from 'node:https';
import zlib from 'node:zlib';
import { StringDecoder } from 'node:string_decoder';

const PORT = Number(process.env.GATEWAY_PORT || 4141);
const ANTHROPIC = new URL(process.env.ANTHROPIC_UPSTREAM || 'https://api.anthropic.com');
const OLLAMA = new URL(process.env.OLLAMA_BASE_URL || 'https://gateway.snet.tu-berlin.de/echelon/ollama');
const OLLAMA_TOKEN = process.env.SECRET_TOM;

if (!OLLAMA_TOKEN) {
  console.error('gateway: SECRET_TOM is not set (expected in ~/.config/claude-gateway/env)');
  process.exit(1);
}

const agents = {
  'http:': new http.Agent({ keepAlive: true }),
  'https:': new https.Agent({ keepAlive: true }),
};
// Hop-by-hop headers: never forwarded in either direction.
const HOP = new Set(['connection', 'keep-alive', 'transfer-encoding', 'proxy-connection', 'te', 'trailer', 'upgrade', 'host']);
// Top-level request fields Ollama's /v1/messages does not accept.
const OLLAMA_DROP_TOP = ['metadata', 'tool_choice', 'thinking', 'context_management', 'output_config'];
// Beta tool-schema fields.
const OLLAMA_DROP_TOOL = ['strict', 'defer_loading', 'input_examples', 'cache_control'];
// Content block types Ollama has no use for.
const OLLAMA_DROP_BLOCK = new Set(['tool_reference', 'redacted_thinking']);

const log = (label, status, t0, detail) =>
  console.log(`${new Date().toISOString()} ${label} ${status} ${Date.now() - t0}ms${detail ? ' ' + detail : ''}`);

const isClaude = (model) => typeof model === 'string' && model.startsWith('claude-');

const readBody = (req) =>
  new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });

// Remove cache_control everywhere and drop unsupported block types, recursively.
function stripBlocks(node) {
  if (Array.isArray(node)) {
    return node.filter((b) => !(b && typeof b === 'object' && OLLAMA_DROP_BLOCK.has(b.type))).map(stripBlocks);
  }
  if (node && typeof node === 'object') {
    delete node.cache_control;
    for (const k of Object.keys(node)) node[k] = stripBlocks(node[k]);
  }
  return node;
}

function sanitizeForOllama(body) {
  for (const k of OLLAMA_DROP_TOP) delete body[k];
  if (body.system !== undefined) body.system = stripBlocks(body.system);
  if (Array.isArray(body.messages)) body.messages = stripBlocks(body.messages);
  if (Array.isArray(body.tools)) {
    body.tools = body.tools
      .filter((t) => !t.type || t.type === 'custom') // drop Anthropic server tools
      .map((t) => {
        for (const k of OLLAMA_DROP_TOOL) delete t[k];
        return t;
      });
  }
  return body;
}

function anthropicHeaders(req, body) {
  const h = {};
  for (const [k, v] of Object.entries(req.headers)) if (!HOP.has(k)) h[k] = v;
  h.host = ANTHROPIC.host;
  h['content-length'] = String(body.length);
  return h;
}

function ollamaHeaders(req, body) {
  return {
    host: OLLAMA.host,
    authorization: `Bearer ${OLLAMA_TOKEN}`,
    'content-type': 'application/json',
    accept: req.headers.accept || 'application/json',
    'anthropic-version': req.headers['anthropic-version'] || '2023-06-01',
    'user-agent': req.headers['user-agent'] || 'claude-gateway',
    'content-length': String(body.length),
  };
}

const ollamaPath = (p) => OLLAMA.pathname.replace(/\/$/, '') + p;

// Read token usage off a successful response without buffering it for the client:
// SSE -> message_start (input/cache) + message_delta (output); JSON -> body.usage.
function usageSink(upRes, onDone) {
  const enc = upRes.headers['content-encoding'];
  const isSSE = /text\/event-stream/i.test(upRes.headers['content-type'] || '');
  let src = upRes;
  if (enc === 'gzip') src = upRes.pipe(zlib.createGunzip());
  else if (enc === 'br') src = upRes.pipe(zlib.createBrotliDecompress());
  else if (enc === 'deflate') src = upRes.pipe(zlib.createInflate());
  const dec = new StringDecoder('utf8');
  const usage = {};
  let buf = '';
  let done = false;
  const merge = (u) => {
    if (u && typeof u === 'object') for (const [k, v] of Object.entries(u)) if (typeof v === 'number') usage[k] = v;
  };
  const finish = (aborted) => { if (!done) { done = true; onDone(usage, aborted); } };
  src.on('data', (c) => {
    buf += dec.write(c);
    if (!isSSE) return;
    const lines = buf.split('\n');
    buf = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data:')) continue;
      let ev;
      try { ev = JSON.parse(line.slice(5)); } catch { continue; }
      if (ev.type === 'message_start') merge(ev.message?.usage);
      else if (ev.type === 'message_delta') merge(ev.usage);
    }
  });
  src.on('end', () => {
    if (!isSSE) { try { merge(JSON.parse(buf + dec.end()).usage); } catch {} }
    finish(false);
  });
  src.on('error', () => finish(true));
  // A decompressor may emit 'end' after the socket closes; only a truncated response is an abort.
  upRes.on('close', () => { if (!upRes.complete) finish(true); });
}

function fmtUsage(u, aborted) {
  const p = [];
  if (u.input_tokens != null) p.push(`in=${u.input_tokens}`);
  if (u.cache_read_input_tokens) p.push(`cache_read=${u.cache_read_input_tokens}`);
  if (u.cache_creation_input_tokens) p.push(`cache_write=${u.cache_creation_input_tokens}`);
  if (u.output_tokens != null) p.push(`out=${u.output_tokens}`);
  if (aborted) p.push('(aborted)');
  return p.join(' ');
}

function decodeForLog(buf, encoding) {
  try {
    if (encoding === 'gzip') return zlib.gunzipSync(buf).toString();
    if (encoding === 'br') return zlib.brotliDecompressSync(buf).toString();
    if (encoding === 'deflate') return zlib.inflateSync(buf).toString();
  } catch {}
  return buf.toString();
}

function forward(req, res, target, { path, headers, body, label }) {
  const t0 = Date.now();
  const mod = target.protocol === 'https:' ? https : http;
  const up = mod.request(
    { protocol: target.protocol, hostname: target.hostname, port: target.port || undefined, method: req.method, path, headers, agent: agents[target.protocol] },
    (upRes) => {
      const h = {};
      for (const [k, v] of Object.entries(upRes.headers)) if (!HOP.has(k)) h[k] = v;
      res.writeHead(upRes.statusCode, h);
      if (upRes.statusCode >= 400) {
        const chunks = [];
        upRes.on('data', (c) => chunks.push(c));
        upRes.on('end', () => log(label, upRes.statusCode, t0, decodeForLog(Buffer.concat(chunks), upRes.headers['content-encoding']).slice(0, 2000)));
      } else {
        usageSink(upRes, (u, aborted) => log(label, upRes.statusCode, t0, fmtUsage(u, aborted)));
      }
      upRes.pipe(res); // streamed as received: SSE pings pass through unbuffered
    },
  );
  up.on('error', (e) => {
    log(label, 502, t0, e.message);
    if (!res.headersSent) res.writeHead(502, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ type: 'error', error: { type: 'api_error', message: `gateway: upstream ${label} failed: ${e.message}` } }));
  });
  res.on('close', () => { if (!res.writableFinished) up.destroy(); });
  up.end(body);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://gateway');
  if (req.method === 'HEAD' && url.pathname === '/api/hello') {
    res.writeHead(200);
    return res.end();
  }

  const body = await readBody(req);
  let json = null;
  if (body.length && /application\/json/i.test(req.headers['content-type'] || '') && !req.headers['content-encoding']) {
    try { json = JSON.parse(body.toString()); } catch {}
  }
  const model = json?.model;

  if (req.method === 'POST' && model && !isClaude(model)) {
    if (url.pathname === '/v1/messages') {
      const out = Buffer.from(JSON.stringify(sanitizeForOllama(json)));
      return forward(req, res, OLLAMA, { path: ollamaPath('/v1/messages'), headers: ollamaHeaders(req, out), body: out, label: `ollama ${model}` });
    }
    if (url.pathname === '/v1/messages/count_tokens') {
      // Ollama has no count_tokens; forwarding it can wedge the server (ollama/ollama#13949).
      res.writeHead(404, { 'content-type': 'application/json' });
      log(`ollama ${model} count_tokens`, 404, Date.now());
      return res.end(JSON.stringify({ type: 'error', error: { type: 'not_found_error', message: `count_tokens unsupported for ${model}` } }));
    }
  }

  // Everything else: transparent pass-through to Anthropic (Authorization + anthropic-beta untouched).
  return forward(req, res, ANTHROPIC, { path: req.url, headers: anthropicHeaders(req, body), body, label: `anthropic ${model ?? `${req.method} ${url.pathname}`}` });
});

server.timeout = 0; // long streams
server.requestTimeout = 0;
server.headersTimeout = 120_000;
server.keepAliveTimeout = 65_000;
server.listen(PORT, '127.0.0.1', () =>
  console.log(`gateway listening on http://127.0.0.1:${PORT}  claude-* -> ${ANTHROPIC.origin}  else -> ${OLLAMA.href}`),
);
