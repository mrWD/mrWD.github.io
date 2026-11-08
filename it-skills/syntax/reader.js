/**
 * Reads code as a syntax tree: what every syntax host does with a request (src/engine/syntax.ts).
 * One copy serves every host — the browser's worker (worker.js beside this file) and Node, for the
 * validator, the tests and the server (scripts/syntax-node.ts). Plain JavaScript, loaded as a
 * script: it defines `SyntaxReader`. Reading code runs none of it, so there is nothing to seal.
 */
(function (root) {
  'use strict';

  /** The leaves of a tree in order: keywords, operators, names, literals, with the node they are in. */
  function leavesOf(rootNode) {
    var out = [];
    var cursor = rootNode.walk();
    var down = true;
    for (;;) {
      if (down && cursor.gotoFirstChild()) continue;
      var node = cursor.currentNode;
      if (node.childCount === 0 && node.text !== '') {
        var leaf = { type: node.type, text: node.text, named: node.isNamed };
        if (node.parent) leaf.parent = node.parent.type;
        out.push(leaf);
      }
      if (cursor.gotoNextSibling()) {
        down = true;
        continue;
      }
      if (!cursor.gotoParent()) break;
      down = false;
    }
    cursor.delete();
    return out;
  }

  /**
   * A reader over web-tree-sitter (`api`: its Parser, Language and Query, initialized) and the
   * grammars `load(lang)` gives (a grammar's bytes, or null for a language without one).
   */
  function create(api, load) {
    var languages = new Map();
    var queries = new Map();

    function language(lang) {
      if (!languages.has(lang))
        languages.set(
          lang,
          Promise.resolve(load(lang)).then(function (bytes) {
            return bytes ? api.Language.load(bytes) : null;
          }),
        );
      return languages.get(lang);
    }

    async function read(request) {
      var lang = request.lang;
      var grammar = await language(lang);
      if (!grammar) return { hasError: false, error: 'no grammar for ' + lang };
      var parser = new api.Parser();
      parser.setLanguage(grammar);
      var tree = parser.parse(request.code);
      try {
        if (!tree) return { hasError: true, error: 'the parser gave no tree' };
        var result = { hasError: tree.rootNode.hasError };
        if (request.query !== undefined) {
          var key = lang + '\n' + request.query;
          var query = queries.get(key);
          if (!query) {
            try {
              query = new api.Query(grammar, request.query);
            } catch (e) {
              return { hasError: result.hasError, error: 'the query does not compile: ' + ((e && e.message) || e) };
            }
            queries.set(key, query);
          }
          result.matches = query.matches(tree.rootNode).map(function (m) {
            return {
              captures: m.captures.map(function (c) {
                return { name: c.name, text: c.node.text, row: c.node.startPosition.row };
              }),
            };
          });
        }
        if (request.leaves) result.leaves = leavesOf(tree.rootNode);
        return result;
      } finally {
        if (tree) tree.delete();
        parser.delete();
      }
    }

    return { read: read, language: language };
  }

  root.SyntaxReader = { create: create };
})(typeof globalThis !== 'undefined' ? globalThis : self);
