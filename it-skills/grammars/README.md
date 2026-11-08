# Grammars

tree-sitter grammars compiled to WebAssembly, one per language, read by `src/engine/syntax.ts`
through a platform's syntax host (`scripts/syntax-node.ts` in Node). A language gets its grammar
here before a course in it uses `ast` checks.

| File | From | Version | License | SHA-256 |
|---|---|---|---|---|
| `tree-sitter-go.wasm` | npm `tree-sitter-go` | 0.25.0 | MIT | `9504573f352b20be7f2f1911754d710622aedc15afff16d5ed8fb5645681aee7` |

The runtime is the `web-tree-sitter` package (0.25.10, MIT), whose ABI these grammars match. To
add a grammar: take the `.wasm` from the language's npm package (`npm pack tree-sitter-<lang>`)
or build it with `tree-sitter build --wasm`, put it here, add a row, and name it in `GRAMMARS`.
