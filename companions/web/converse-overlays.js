/*
 * Cam converse overlays — vanilla mirror of shared/converseOverlays.ts for the
 * on-device companion (no bundler). Reads config/persona/converse-overlays.json
 * so the companion answers with the same phrases as both servers.
 *
 * UMD: window.CamOverlays in the browser, module.exports under Node (parity check).
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.CamOverlays = api;
})(
  typeof self !== "undefined" ? self : typeof globalThis !== "undefined" ? globalThis : this,
  function () {
  "use strict";

  var DEFAULT_INTENT_ORDER = ["greeting", "mic_check", "ack", "presence_chatter"];
  var DEFAULT_SPEAK = { rate: 0.95, pitch: 1.05, lang: "en-US" };
  var FALLBACK = {
    version: 0,
    id: "converse-overlays-fallback",
    empty: "I'm here, Aaron. Whenever you're ready — I'm listening.",
    overlays: [],
    intent_rules: {},
    intent_order: DEFAULT_INTENT_ORDER,
    intents: {},
    echo: "I heard you: “{short}”. Tell me the next step and I'll take it from there.",
    short_max: 120,
  };
  var CONFIG_PATH = "config/persona/converse-overlays.json";
  var STORAGE_KEY = "cam.converse.overlays.v1";
  var regexCache = {};

  function escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function wordHit(low, word) {
    return new RegExp("\\b" + escapeRegex(word) + "\\b").test(low);
  }

  function includesAny(low, phrases) {
    for (var i = 0; i < phrases.length; i++) {
      if (low.indexOf(phrases[i]) !== -1) return true;
    }
    return false;
  }

  function ruleMatches(low, rule) {
    var anyPhrases = rule.any || [];
    if (anyPhrases.length && includesAny(low, anyPhrases)) return true;
    var words = rule.words || [];
    for (var i = 0; i < words.length; i++) {
      if (wordHit(low, words[i])) return true;
    }
    var groups = rule.all_groups || [];
    if (groups.length) {
      var all = true;
      for (var g = 0; g < groups.length; g++) {
        if (!includesAny(low, groups[g])) {
          all = false;
          break;
        }
      }
      if (all) return true;
    }
    return false;
  }

  function matchOverlay(low, cfg) {
    var rules = (cfg && cfg.overlays) || [];
    for (var i = 0; i < rules.length; i++) {
      if (ruleMatches(low, rules[i])) return rules[i];
    }
    return null;
  }

  function intentOrder(cfg) {
    var order = cfg && cfg.intent_order && cfg.intent_order.length ? cfg.intent_order : DEFAULT_INTENT_ORDER;
    return order.map(String);
  }

  function intentRegex(name, pattern) {
    var key = name + ":" + pattern;
    if (!regexCache[key]) regexCache[key] = new RegExp(pattern, "i");
    return regexCache[key];
  }

  function classifyIntents(text, cfg) {
    var rules = (cfg && cfg.intent_rules) || {};
    var t = (text || "").trim();
    var hits = [];
    var order = intentOrder(cfg);
    for (var i = 0; i < order.length; i++) {
      var spec = rules[order[i]];
      if (!spec || !spec.regex) continue;
      if (intentRegex(order[i], spec.regex).test(t)) hits.push(order[i]);
    }
    return hits;
  }

  function lastAaronLine(history) {
    if (!history) return "";
    for (var i = history.length - 1; i >= 0; i--) {
      var row = history[i];
      if (!row || typeof row !== "object") continue;
      if (typeof row.aaron === "string" && row.aaron) return row.aaron;
      if (row.role === "aaron" && typeof row.text === "string" && row.text) return row.text;
    }
    return "";
  }

  function shorten(text, cfg) {
    var limit = Number((cfg && cfg.short_max) || 120);
    var chars = Array.from(text);
    return chars.length < limit ? text : chars.slice(0, limit - 3).join("") + "…";
  }

  function speakParams(cfg) {
    var out = { rate: DEFAULT_SPEAK.rate, pitch: DEFAULT_SPEAK.pitch, lang: DEFAULT_SPEAK.lang };
    var s = (cfg && cfg.speak) || {};
    if (typeof s.rate === "number") out.rate = s.rate;
    if (typeof s.pitch === "number") out.pitch = s.pitch;
    if (typeof s.lang === "string" && s.lang) out.lang = s.lang;
    if (typeof s.style === "string" && s.style) out.style = s.style;
    return out;
  }

  function fill(template, vars) {
    return template.replace(/\{(\w+)\}/g, function (m, k) {
      return Object.prototype.hasOwnProperty.call(vars, k) ? vars[k] : m;
    });
  }

  function explainReply(aaronText, trace, history, cfg) {
    cfg = cfg || FALLBACK;
    trace = trace || {};
    var t = (aaronText || "").trim();
    if (!t) return { text: cfg.empty || "I'm here, Aaron.", kind: "empty", id: null };
    var low = t.toLowerCase();
    var rule = matchOverlay(low, cfg);
    if (rule) return { text: rule.reply || "", kind: "overlay", id: String(rule.id || "") };
    var intents = trace.intents && trace.intents.length ? trace.intents.slice() : [];
    if (!intents.length) intents = classifyIntents(t, cfg);
    var intentReplies = cfg.intents || {};
    var order = intentOrder(cfg);
    for (var i = 0; i < order.length; i++) {
      var key = order[i];
      if (intents.indexOf(key) !== -1 && intentReplies[key]) {
        return { text: intentReplies[key], kind: "intent", id: key };
      }
    }
    if ((trace.path || "") === "slow") {
      var hotspot = trace.hotspot_id || "capability";
      var motors = (trace.motor_plan && trace.motor_plan.length ? trace.motor_plan : ["motor.mesh"]).join(", ");
      return {
        text: fill(cfg.slow_plan || "I have a plan.", { hotspot: hotspot, motors: motors }),
        kind: "slow_plan",
        id: String(hotspot),
      };
    }
    var short = shorten(t, cfg);
    var previous = lastAaronLine(history).trim().toLowerCase();
    if (previous && previous === low && cfg.echo_repeat) {
      return { text: fill(cfg.echo_repeat, { short: short }), kind: "echo_repeat", id: null };
    }
    return { text: fill(cfg.echo || "I heard you: “{short}”.", { short: short }), kind: "echo", id: null };
  }

  /* Browser helpers: fetch once, keep the last good copy for offline turns. */
  function readCached(storage) {
    try {
      var raw = storage && storage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function writeCached(storage, cfg) {
    try {
      if (storage) storage.setItem(STORAGE_KEY, JSON.stringify(cfg));
    } catch (e) {
      /* quota / private mode — keep going */
    }
  }

  function load(opts) {
    opts = opts || {};
    var storage = opts.storage !== undefined ? opts.storage : typeof localStorage !== "undefined" ? localStorage : null;
    var url = opts.url || CONFIG_PATH;
    var fetchFn = opts.fetch || (typeof fetch === "function" ? fetch.bind(root) : null);
    var cached = readCached(storage);
    if (!fetchFn) return Promise.resolve({ cfg: cached || FALLBACK, source: cached ? "cache" : "fallback" });
    return fetchFn(url, { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("overlays " + res.status);
        return res.json();
      })
      .then(function (cfg) {
        if (!cfg || typeof cfg !== "object" || !Array.isArray(cfg.overlays)) throw new Error("overlays shape");
        writeCached(storage, cfg);
        return { cfg: cfg, source: "network" };
      })
      .catch(function () {
        return { cfg: cached || FALLBACK, source: cached ? "cache" : "fallback" };
      });
  }

  return {
    CONFIG_PATH: CONFIG_PATH,
    STORAGE_KEY: STORAGE_KEY,
    FALLBACK: FALLBACK,
    DEFAULT_INTENT_ORDER: DEFAULT_INTENT_ORDER,
    ruleMatches: ruleMatches,
    matchOverlay: matchOverlay,
    classifyIntents: classifyIntents,
    intentOrder: intentOrder,
    lastAaronLine: lastAaronLine,
    shorten: shorten,
    speakParams: speakParams,
    explainReply: explainReply,
    load: load,
  };
  }
);
