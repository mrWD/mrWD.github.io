/**
 * The browser's syntax host: web-tree-sitter in a module worker, with the grammars of
 * public/grammars/ (src/components/SyntaxHost.web.tsx starts it). Messages:
 * `{ type: 'init', grammars: { go: 'tree-sitter-go.wasm' } }` first, then
 * `{ id, lang, code, query?, leaves? }`; out, `{ type: 'ready' }` or `{ type: 'failed', error }`,
 * then `{ type: 'result', id, ...SyntaxResult }`. The rules are reader.js, as in Node.
 */
import { Language, Parser, Query } from './tree-sitter.js';
import './reader.js';

const base = new URL('./', self.location.href);
let reader = null;
const waiting = [];

async function start(grammars) {
  await Parser.init({ locateFile: (file) => new URL(file, base).href });
  reader = self.SyntaxReader.create({ Parser, Language, Query }, async (lang) => {
    const file = grammars[lang];
    if (!file) return null;
    const response = await fetch(new URL(`../grammars/${file}`, base));
    return response.ok ? new Uint8Array(await response.arrayBuffer()) : null;
  });
}

async function answer(request) {
  try {
    self.postMessage({ type: 'result', id: request.id, ...(await reader.read(request)) });
  } catch (e) {
    self.postMessage({ type: 'result', id: request.id, hasError: false, error: String((e && e.message) || e) });
  }
}

self.onmessage = (event) => {
  const message = event.data;
  if (message.type === 'init') {
    start(message.grammars).then(
      () => {
        self.postMessage({ type: 'ready' });
        for (const request of waiting.splice(0)) answer(request);
      },
      (e) => self.postMessage({ type: 'failed', error: String((e && e.message) || e) }),
    );
  } else if (reader) answer(message);
  else waiting.push(message);
};
