/**
 * Trait Lab — browser port of thinkbox/trait_game/engine.py.
 *
 * Same LCG (1664525), same bag order, same actions. Game id trait-lab.
 * Local play only. live_verified stays false. No wallet and no chain.
 */
(function (global) {
  "use strict";

  var GAME_ID = "trait-lab";
  var LCG_MULT = 1664525;
  var LCG_INC = 1013904223;
  var GRADE_ORDER = { S: 5, A: 4, B: 3, C: 2, D: 1 };
  var BOARD_KEY = "trait-lab-board";
  var RUN_KEY = "trait-lab-run";

  function TraitGameError(code, message) {
    this.code = code;
    this.message = message;
    this.name = "TraitGameError";
  }

  function isGameError(exc) {
    return exc && exc.name === "TraitGameError";
  }

  function dailySeed(day) {
    var parts = String(day).split("-");
    if (parts.length !== 3 || parts.some(function (part) { return !/^\d+$/.test(part); })) {
      throw new TraitGameError("invalid_day", "daily seed requires YYYY-MM-DD");
    }
    var year = parseInt(parts[0], 10);
    var month = parseInt(parts[1], 10);
    var date = parseInt(parts[2], 10);
    if (!(month >= 1 && month <= 12 && date >= 1 && date <= 31)) {
      throw new TraitGameError("invalid_day", "daily seed requires a real calendar day");
    }
    return year * 10000 + month * 100 + date;
  }

  function step(rng) {
    return (rng * LCG_MULT + LCG_INC) >>> 0;
  }

  function traits(rules) {
    var rows = [];
    var rarities = rules.rarity_by_index;
    Object.keys(rules.collections).forEach(function (collection) {
      rules.collections[collection].forEach(function (name, index) {
        rows.push({
          collection: collection,
          name: name,
          index: index,
          rarity: rarities[index],
        });
      });
    });
    return rows;
  }

  function findTrait(rules, collection, name) {
    var rows = traits(rules);
    for (var i = 0; i < rows.length; i += 1) {
      if (rows[i].collection === collection && rows[i].name === name) return rows[i];
    }
    throw new TraitGameError("unknown_trait", "unknown trait " + collection + "/" + name);
  }

  function owned(state, collection, name) {
    return (state.inventory[collection] || []).indexOf(name) !== -1;
  }

  function rankOf(rules, rarity) {
    return rules.rarity_by_index.indexOf(rarity);
  }

  function bagWeights(rules, state, risk) {
    var focus = state.focus || "";
    var multiplier = rules.focus_multiplier;
    var items = [];
    traits(rules).forEach(function (row) {
      if (risk && row.rarity === "common") return;
      var weight = rules.weights[row.rarity];
      if (focus && row.collection === focus) weight *= multiplier;
      items.push([row, weight]);
    });
    return items;
  }

  function pick(rules, state, risk) {
    var items = bagWeights(rules, state, risk);
    if (!items.length) {
      throw new TraitGameError("no_risk_targets", "risk draw has no rare-or-better traits");
    }
    var total = items.reduce(function (sum, item) { return sum + item[1]; }, 0);
    var rng = step(state.rng >>> 0);
    state.rng = rng;
    var roll = rng % total;
    var cursor = 0;
    for (var i = 0; i < items.length; i += 1) {
      cursor += items[i][1];
      if (roll < cursor) return items[i][0];
    }
    return items[items.length - 1][0];
  }

  function comboMultiplier(rules, combo) {
    var capped = Math.min(Math.max(combo, 0), rules.combo_cap);
    return 1 + rules.combo_step * capped;
  }

  function refreshRival(rules, state) {
    var pace = rules.difficulties[state.difficulty].rival_per_turn;
    state.rival_xp = state.turn * pace;
  }

  function gradeOf(state) {
    var sets = state.completed.length;
    var ahead = state.xp >= state.rival_xp;
    if (sets >= 5) return "S";
    if (ahead && sets >= 3) return "A";
    if (ahead && sets >= 1) return "B";
    if (sets >= 1) return "C";
    return "D";
  }

  function addAchievement(state, name) {
    if (state.achievements.indexOf(name) === -1) state.achievements.push(name);
  }

  function achievements(state) {
    var anyOwned = Object.keys(state.inventory).some(function (key) {
      return state.inventory[key].length > 0;
    });
    if (anyOwned) addAchievement(state, "spark");
    if (state.completed.length) addAchievement(state, "bound");
    if (state.combo >= 3) addAchievement(state, "chain");
    if (state.dust >= 8) addAchievement(state, "residue");
    if (state.turn >= 3 && state.xp >= state.rival_xp) addAchievement(state, "ahead");
    if (state.completed.length >= 3) addAchievement(state, "atlas");
    if (state.difficulty === "thesis" && state.over && (gradeOf(state) === "S" || gradeOf(state) === "A")) {
      addAchievement(state, "thesis");
    }
  }

  function maybeClose(rules, state) {
    var limit = rules.difficulties[state.difficulty].turns;
    if (state.turn >= limit) {
      state.over = true;
      state.grade = gradeOf(state);
    }
    achievements(state);
  }

  function synergyGain(rules, state) {
    var gained = [];
    rules.synergies.forEach(function (item) {
      if (state.synergies.indexOf(item.id) !== -1) return;
      if (owned(state, item.a[0], item.a[1]) && owned(state, item.b[0], item.b[1])) {
        state.synergies.push(item.id);
        state.xp += item.xp;
        gained.push(item.id);
      }
    });
    return gained;
  }

  function grant(rules, state, row, action, energySpent) {
    var collection = row.collection;
    var name = row.name;
    var comboBefore = state.combo;
    var event = {
      action: action,
      collection: collection,
      trait: name,
      rarity: row.rarity,
      energy_spent: energySpent,
      combo_before: comboBefore,
      duplicate: false,
      set_completed: false,
      jackpot: false,
      synergies: [],
      shield_consumed: false,
      xp_delta: 0,
      dust_delta: 0,
    };
    if (owned(state, collection, name)) {
      var dust = 1 + rankOf(rules, row.rarity) * rules.dust_per_duplicate_rank;
      state.dust += dust;
      state.combo = 0;
      event.duplicate = true;
      event.dust_delta = dust;
    } else {
      if (!state.inventory[collection]) state.inventory[collection] = [];
      state.inventory[collection].push(name);
      state.combo = comboBefore + 1;
      var gained = Math.trunc(rules.xp_by_rarity[row.rarity] * comboMultiplier(rules, state.combo));
      if (state.shield_armed) {
        gained = Math.trunc(gained * rules.shield_multiplier);
        state.shield_armed = false;
        event.shield_consumed = true;
      }
      state.xp += gained;
      event.xp_delta += gained;
      var ownedNow = state.inventory[collection];
      var names = rules.collections[collection];
      if (state.completed.indexOf(collection) === -1 && names.every(function (trait) {
        return ownedNow.indexOf(trait) !== -1;
      })) {
        var bonus = rules.set_bonus[collection];
        state.xp += bonus;
        event.xp_delta += bonus;
        event.set_completed = true;
        state.completed.push(collection);
        if (state.combo >= rules.jackpot_combo) {
          state.xp += rules.jackpot_xp;
          event.xp_delta += rules.jackpot_xp;
          event.jackpot = true;
        }
      }
      var synergies = synergyGain(rules, state);
      event.synergies = synergies;
      event.xp_delta += synergies.reduce(function (sum, sid) {
        var match = rules.synergies.filter(function (item) { return item.id === sid; })[0];
        return sum + (match ? match.xp : 0);
      }, 0);
    }
    state.turn += 1;
    refreshRival(rules, state);
    state.log.push(event);
    maybeClose(rules, state);
    return event;
  }

  function newRun(rules, seed, difficulty) {
    difficulty = difficulty || "lab";
    if (!rules.difficulties[difficulty]) {
      throw new TraitGameError("unknown_difficulty", "unknown difficulty " + difficulty);
    }
    if (!(seed > 0)) throw new TraitGameError("invalid_seed", "seed must be a positive integer");
    var profile = rules.difficulties[difficulty];
    var inventory = {};
    Object.keys(rules.collections).forEach(function (name) { inventory[name] = []; });
    return {
      game_id: rules.game_id || GAME_ID,
      version: rules.version,
      seed: seed,
      rng: seed >>> 0,
      difficulty: difficulty,
      turn: 0,
      turns_max: profile.turns,
      energy: profile.energy,
      energy_max: profile.energy,
      dust: 0,
      xp: 0,
      rival_xp: 0,
      combo: 0,
      focus: "",
      shield_armed: false,
      mulligan_used: false,
      inventory: inventory,
      completed: [],
      synergies: [],
      achievements: [],
      log: [],
      undo: null,
      over: false,
      grade: "",
      live_verified: false,
    };
  }

  function cloneLog(entry) {
    var copy = {};
    Object.keys(entry).forEach(function (key) {
      copy[key] = Array.isArray(entry[key]) ? entry[key].slice() : entry[key];
    });
    return copy;
  }

  function cloneState(state) {
    var inventory = {};
    Object.keys(state.inventory).forEach(function (key) {
      inventory[key] = state.inventory[key].slice();
    });
    return {
      game_id: state.game_id,
      version: state.version,
      seed: state.seed,
      rng: state.rng,
      difficulty: state.difficulty,
      turn: state.turn,
      turns_max: state.turns_max,
      energy: state.energy,
      energy_max: state.energy_max,
      dust: state.dust,
      xp: state.xp,
      rival_xp: state.rival_xp,
      combo: state.combo,
      focus: state.focus,
      shield_armed: state.shield_armed,
      mulligan_used: state.mulligan_used,
      inventory: inventory,
      completed: state.completed.slice(),
      synergies: state.synergies.slice(),
      achievements: state.achievements.slice(),
      log: state.log.map(cloneLog),
      undo: state.undo ? cloneState(state.undo) : null,
      over: state.over,
      grade: state.grade,
      live_verified: false,
    };
  }

  function snapshot(state) {
    var saved = cloneState(state);
    saved.undo = null;
    return saved;
  }

  function spendEnergy(state, cost) {
    if (state.energy < cost) throw new TraitGameError("insufficient_energy", "not enough energy");
    state.energy -= cost;
  }

  function requireOpen(state) {
    if (state.over) throw new TraitGameError("run_complete", "the run is already over");
  }

  function acquire(rules, state, action, risk) {
    var cost = rules.energy_cost[action];
    spendEnergy(state, cost);
    return grant(rules, state, pick(rules, state, risk), action, cost);
  }

  function forge(rules, state, collection, name) {
    if (!rules.collections[collection]) {
      throw new TraitGameError("unknown_collection", "unknown collection " + collection);
    }
    var row = findTrait(rules, collection, name);
    if (owned(state, collection, name)) {
      throw new TraitGameError("already_owned", "that trait is already in the lab");
    }
    var cost = rules.forge_dust_base + rankOf(rules, row.rarity);
    if (state.dust < cost) throw new TraitGameError("insufficient_dust", "not enough dust to forge");
    state.dust -= cost;
    var event = grant(rules, state, row, "forge", 0);
    event.dust_delta -= cost;
    return event;
  }

  function mulligan(rules, state) {
    if (state.mulligan_used) throw new TraitGameError("mulligan_spent", "mulligan was already used");
    var last = state.log[state.log.length - 1];
    if (!last || (last.action !== "draw" && last.action !== "risk_draw")) {
      throw new TraitGameError("nothing_to_mulligan", "mulligan only reverses the last draw");
    }
    if (last.duplicate) {
      state.dust -= last.dust_delta;
      state.combo = last.combo_before;
    } else {
      var held = state.inventory[last.collection] || [];
      var at = held.indexOf(last.trait);
      if (at !== -1) held.splice(at, 1);
      if (last.set_completed) {
        var doneAt = state.completed.indexOf(last.collection);
        if (doneAt !== -1) state.completed.splice(doneAt, 1);
      }
      (last.synergies || []).forEach(function (sid) {
        var syn = state.synergies.indexOf(sid);
        if (syn !== -1) state.synergies.splice(syn, 1);
      });
      state.xp -= last.xp_delta;
      state.combo = last.combo_before;
      if (last.shield_consumed) state.shield_armed = true;
    }
    state.energy += last.energy_spent;
    state.turn = Math.max(0, state.turn - 1);
    state.log.pop();
    state.mulligan_used = true;
    state.over = false;
    state.grade = "";
    refreshRival(rules, state);
    var note = { action: "mulligan", collection: last.collection || "", trait: last.trait || "" };
    state.log.push(note);
    achievements(state);
    return note;
  }

  function act(rules, state, action, args) {
    args = args || {};
    var original = cloneState(state);
    var working = cloneState(state);
    var event = null;
    try {
      requireOpen(working);
      if (action === "undo") {
        if (!working.undo) throw new TraitGameError("nothing_to_undo", "no action to undo");
        var restored = working.undo;
        restored.undo = null;
        return { ok: true, error: "", state: restored, event: { action: "undo" } };
      }
      working.undo = snapshot(working);
      if (action === "draw") event = acquire(rules, working, "draw", false);
      else if (action === "risk_draw") event = acquire(rules, working, "risk_draw", true);
      else if (action === "focus") {
        var collection = String(args.collection || "");
        if (!rules.collections[collection]) {
          throw new TraitGameError("unknown_collection", "unknown collection " + collection);
        }
        working.focus = collection;
        event = { action: "focus", collection: collection, trait: "" };
        working.log.push(event);
      } else if (action === "forge") {
        event = forge(rules, working, String(args.collection || ""), String(args.trait || ""));
      } else if (action === "mulligan") event = mulligan(rules, working);
      else if (action === "arm_shield") {
        if (working.shield_armed) throw new TraitGameError("shield_armed", "a shield is already armed");
        spendEnergy(working, rules.energy_cost.arm_shield);
        working.shield_armed = true;
        event = { action: "arm_shield", collection: "", trait: "" };
        working.log.push(event);
      } else if (action === "finish") {
        working.over = true;
        refreshRival(rules, working);
        working.grade = gradeOf(working);
        achievements(working);
        event = { action: "finish", collection: "", trait: "" };
        working.log.push(event);
      } else {
        throw new TraitGameError("unknown_action", "unknown action " + action);
      }
    } catch (exc) {
      if (!isGameError(exc)) throw exc;
      return { ok: false, error: exc.code, state: original, event: null };
    }
    return { ok: true, error: "", state: working, event: event };
  }

  function proofBody(state) {
    return {
      game_id: state.game_id,
      version: state.version,
      seed: state.seed,
      difficulty: state.difficulty,
      xp: state.xp,
      rival_xp: state.rival_xp,
      turn: state.turn,
      completed: state.completed.slice(),
      synergies: state.synergies.slice(),
      grade: state.grade || (state.over ? gradeOf(state) : ""),
      log_actions: state.log.map(function (entry) { return entry.action; }),
      live_verified: false,
    };
  }

  function canonical(value) {
    if (value === null || typeof value !== "object") return JSON.stringify(value);
    if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
    var keys = Object.keys(value).sort();
    return "{" + keys.map(function (key) {
      return JSON.stringify(key) + ":" + canonical(value[key]);
    }).join(",") + "}";
  }

  function hexBytes(buffer) {
    return Array.from(new Uint8Array(buffer)).map(function (byte) {
      return byte.toString(16).padStart(2, "0");
    }).join("");
  }

  function proofScorecard(state) {
    return crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical(proofBody(state)))).then(function (digest) {
      var body = proofBody(state);
      body.proof_sha256 = hexBytes(digest);
      return body;
    });
  }

  function rankBoard(entries, limit) {
    limit = limit || 10;
    return entries.slice().sort(function (a, b) {
      var xpDelta = (b.xp || 0) - (a.xp || 0);
      if (xpDelta) return xpDelta;
      var gradeDelta = (GRADE_ORDER[b.grade] || 0) - (GRADE_ORDER[a.grade] || 0);
      if (gradeDelta) return gradeDelta;
      return (a.turn || 0) - (b.turn || 0);
    }).slice(0, Math.max(1, limit));
  }

  function forgeCost(rules, rarity) {
    return rules.forge_dust_base + rankOf(rules, rarity);
  }

  var ERROR_TEXT = {
    insufficient_energy: "Not enough energy for that action.",
    no_risk_targets: "Risk draw has nothing above common.",
    unknown_collection: "That collection is not in the lab.",
    unknown_trait: "That trait is not in the rules.",
    already_owned: "You already hold that trait. Draw it again for dust.",
    insufficient_dust: "Not enough dust to forge that trait.",
    mulligan_spent: "The mulligan is already spent.",
    nothing_to_mulligan: "Mulligan only reverses the last draw.",
    run_complete: "This run is closed. Start another seed.",
    nothing_to_undo: "Nothing to undo.",
    shield_armed: "A shield is already armed.",
    unknown_action: "That action is not in the rules.",
    unknown_difficulty: "Pick survey, lab, or thesis.",
    invalid_seed: "Seed must be a positive integer.",
    invalid_day: "Daily seed needs a real calendar day.",
  };

  function esc(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function readJson(key, fallback) {
    try {
      var raw = global.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (err) {
      return fallback;
    }
  }

  function writeJson(key, value) {
    try {
      global.localStorage.setItem(key, JSON.stringify(value));
    } catch (err) {
      /* private mode can reject storage; the run still plays */
    }
  }

  var rules = null;
  var state = null;
  var ui = {
    collection: "eyes",
    trait: "",
    name: "operator",
    note: "Draw spends 1 energy. Risk skips commons and spends 2. Focus does not spend a turn.",
    proof: "",
  };

  function standing() {
    if (!state) return "—";
    return state.grade || gradeOf(state);
  }

  function describe(event) {
    if (!event) return "";
    if (event.action === "undo") return "Undid the previous action.";
    if (event.action === "focus") return "Focus lens locked on " + event.collection + ".";
    if (event.action === "arm_shield") return "Shield armed. The next new trait scores ×1.5.";
    if (event.action === "finish") return "Run filed. Grade " + state.grade + ".";
    if (event.action === "mulligan") return "Mulligan returned " + event.trait + ".";
    var bits = [event.rarity + " " + event.trait];
    if (event.duplicate) bits.push("duplicate → " + event.dust_delta + " dust, combo reset");
    else bits.push("+" + event.xp_delta + " XP");
    if (event.set_completed) bits.push(event.collection + " set bound");
    if (event.jackpot) bits.push("jackpot");
    if (event.synergies && event.synergies.length) bits.push("synergy " + event.synergies.join(", "));
    if (event.shield_consumed) bits.push("shield spent");
    return bits.join(" · ");
  }

  function selectedRow() {
    if (!rules || !ui.trait) return null;
    try {
      return findTrait(rules, ui.collection, ui.trait);
    } catch (err) {
      return null;
    }
  }

  function render() {
    var root = document.getElementById("lab");
    if (!root || !rules || !state) return;
    var metrics = document.getElementById("lab-metrics");
    var actions = document.getElementById("lab-actions");
    var boards = document.getElementById("lab-boards");
    var log = document.getElementById("lab-log");
    var proof = document.getElementById("lab-proof");
    var board = document.getElementById("lab-board");
    var systems = document.getElementById("lab-systems");
    var banner = document.getElementById("lab-banner");
    var ahead = state.xp >= state.rival_xp;
    var span = Math.max(state.xp, state.rival_xp, 1);
    var row = selectedRow();
    var cost = row ? forgeCost(rules, row.rarity) : 0;
    var last = state.log[state.log.length - 1];
    var canMulligan = !state.over && !state.mulligan_used && last && (last.action === "draw" || last.action === "risk_draw");

    banner.innerHTML = state.over
      ? "<strong>Grade " + esc(state.grade) + "</strong> filed on seed " + esc(state.seed) + ". This scorecard is local and not live-verified."
      : "Seeded lab. No wallet, no mint, no chain. <span>live_verified: false</span>";

    metrics.innerHTML = [
      ["Turn", state.turn + " / " + state.turns_max],
      ["Energy", state.energy + " / " + state.energy_max],
      ["XP", String(state.xp)],
      ["Rival", String(state.rival_xp)],
      ["Combo", "×" + state.combo],
      ["Dust", String(state.dust)],
    ].map(function (pair) {
      return "<div class=\"lab-metric\"><span>" + esc(pair[0]) + "</span><strong>" + esc(pair[1]) + "</strong></div>";
    }).join("") +
      "<div class=\"lab-race\" aria-label=\"Pace against the rival\">" +
      "<div class=\"lab-race-label\"><span>You " + esc(state.xp) + "</span><span>" + (state.xp === state.rival_xp ? "tied" : (ahead ? "ahead" : "behind")) + "</span><span>Rival " + esc(state.rival_xp) + "</span></div>" +
      "<div class=\"lab-race-track\"><i class=\"you\" style=\"width:" + Math.min(100, (state.xp / span) * 100) + "%\"></i><i class=\"rival\" style=\"width:" + Math.min(100, (state.rival_xp / span) * 100) + "%\"></i></div></div>" +
      "<p class=\"lab-note\" role=\"status\">" + esc(ui.note) + "</p>" +
      "<div class=\"lab-flags\">" +
      "<span>Standing " + esc(standing()) + "</span>" +
      "<span>Focus " + esc(state.focus || "none") + "</span>" +
      "<span>Shield " + (state.shield_armed ? "armed" : "down") + "</span>" +
      "<span>Mulligan " + (state.mulligan_used ? "spent" : "ready") + "</span>" +
      (state.achievements.length ? "<span>" + esc(state.achievements.join(" · ")) + "</span>" : "") +
      (state.synergies.length ? "<span>Synergy " + esc(state.synergies.join(" · ")) + "</span>" : "") +
      "</div>";

    actions.innerHTML =
      "<button type=\"button\" class=\"btn btn-primary\" data-act=\"draw\"" + (state.over || state.energy < 1 ? " disabled" : "") + ">Draw · 1</button>" +
      "<button type=\"button\" class=\"btn btn-secondary\" data-act=\"risk_draw\"" + (state.over || state.energy < 2 ? " disabled" : "") + ">Risk · 2</button>" +
      "<button type=\"button\" class=\"btn btn-secondary\" data-act=\"focus\"" + (state.over ? " disabled" : "") + ">Focus " + esc(ui.collection) + "</button>" +
      "<button type=\"button\" class=\"btn btn-secondary\" data-act=\"forge\"" + (state.over || !row || owned(state, ui.collection, ui.trait) || state.dust < cost ? " disabled" : "") + ">Forge" + (row ? " · " + cost + " dust" : "") + "</button>" +
      "<button type=\"button\" class=\"btn btn-ghost\" data-act=\"arm_shield\"" + (state.over || state.shield_armed || state.energy < 1 ? " disabled" : "") + ">Shield · 1</button>" +
      "<button type=\"button\" class=\"btn btn-ghost\" data-act=\"mulligan\"" + (canMulligan ? "" : " disabled") + ">Mulligan</button>" +
      "<button type=\"button\" class=\"btn btn-ghost\" data-act=\"undo\"" + (!state.over && state.undo ? "" : " disabled") + ">Undo</button>" +
      "<button type=\"button\" class=\"btn btn-primary\" data-act=\"finish\"" + (state.over ? " disabled" : "") + ">File grade</button>";

    boards.innerHTML = Object.keys(rules.collections).map(function (collection) {
      var names = rules.collections[collection];
      var held = state.inventory[collection] || [];
      var complete = state.completed.indexOf(collection) !== -1;
      var width = Math.round((held.length / names.length) * 100);
      return "<article class=\"card challenge-card" + (complete ? " is-complete" : "") + (state.focus === collection ? " is-focus" : "") + "\">" +
        "<div class=\"challenge-header\"><button type=\"button\" class=\"challenge-title\" data-focus=\"" + esc(collection) + "\">" + esc(collection) + "</button>" +
        "<span class=\"challenge-reward\">+" + esc(rules.set_bonus[collection]) + " set</span></div>" +
        "<div class=\"challenge-progress\"><div class=\"challenge-bar\"><div class=\"challenge-bar-fill\" style=\"width:" + width + "%\"></div></div>" +
        "<span class=\"challenge-count\">" + held.length + "/" + names.length + (complete ? " bound" : "") + "</span></div>" +
        "<div class=\"challenge-traits\">" + names.map(function (name) {
          var meta = findTrait(rules, collection, name);
          var have = held.indexOf(name) !== -1;
          var selected = ui.collection === collection && ui.trait === name;
          return "<button type=\"button\" class=\"trait rarity-" + esc(meta.rarity) + (have ? " owned" : "") + (selected ? " is-selected" : "") + "\" data-collection=\"" + esc(collection) + "\" data-trait=\"" + esc(name) + "\">" +
            esc(name) + "<small>" + esc(meta.rarity) + " · " + forgeCost(rules, meta.rarity) + "</small></button>";
        }).join("") + "</div></article>";
    }).join("");

    var lines = state.log.slice().reverse().slice(0, 12);
    log.innerHTML = "<h3>Replay</h3>" + (lines.length ? "<ol>" + lines.map(function (entry) {
      var label = entry.action + (entry.trait ? " · " + entry.trait : "");
      var marks = "";
      if (entry.xp_delta) marks += "<em>+" + esc(entry.xp_delta) + "</em>";
      if (entry.dust_delta) marks += "<em>" + (entry.dust_delta > 0 ? "+" : "") + esc(entry.dust_delta) + " dust</em>";
      return "<li><span>" + esc(label) + "</span>" + marks + "</li>";
    }).join("") + "</ol>" : "<p class=\"text-muted\">No actions yet. The log is the replay.</p>");

    proof.innerHTML = "<h3>Scorecard</h3><p>Canonical record for this seed. The hash is local. It is not a live proof.</p>" +
      "<code>" + esc(ui.proof || "scoring…") + "</code>" +
      "<p class=\"text-muted\">" + esc(state.game_id) + " v" + esc(state.version) + " · " + esc(state.difficulty) + " · seed " + esc(state.seed) + "</p>";

    var ranked = rankBoard(readJson(BOARD_KEY, []), 8);
    board.innerHTML = "<h3>This browser</h3><p>Names you choose. Sorted by XP, then grade, then fewer turns.</p>" +
      (ranked.length ? "<div class=\"leaderboard-list\">" + ranked.map(function (entry, index) {
        return "<div class=\"card leaderboard-item\"><span class=\"rank" + (index < 3 ? " rank-" + (index + 1) : "") + "\">" + (index + 1) + "</span>" +
          "<span class=\"player\">" + esc(entry.name || "operator") + "</span>" +
          "<span class=\"score\">" + esc(entry.xp) + " · " + esc(entry.grade || "—") + "</span></div>";
      }).join("") + "</div>" : "<p class=\"text-muted\">No filed runs on this browser yet.</p>") +
      "<button type=\"button\" class=\"btn btn-ghost\" id=\"lab-clear-board\">Clear local board</button>";

    systems.innerHTML = "<h3>25 systems</h3><ul>" + rules.updates.map(function (item) {
      return "<li><strong>" + esc(item.id) + "</strong> " + esc(item.name.replace(/_/g, " ")) + "</li>";
    }).join("") + "</ul>";
  }

  function remember() {
    writeJson(RUN_KEY, { state: state, ui: { collection: ui.collection, trait: ui.trait, name: ui.name } });
  }

  function fileScore() {
    if (!state || !state.over) return;
    var board = readJson(BOARD_KEY, []);
    var name = (ui.name || "operator").trim().slice(0, 24) || "operator";
    var fingerprint = [state.seed, state.difficulty, state.xp, state.turn, state.grade, state.log.length].join(":");
    if (board.some(function (entry) { return entry.fingerprint === fingerprint && entry.name === name; })) return;
    board.push({
      name: name,
      xp: state.xp,
      grade: state.grade,
      turn: state.turn,
      seed: state.seed,
      difficulty: state.difficulty,
      fingerprint: fingerprint,
    });
    writeJson(BOARD_KEY, board.slice(-40));
  }

  function refreshProof() {
    var ticket = state;
    proofScorecard(state).then(function (card) {
      if (ticket !== state) return;
      ui.proof = card.proof_sha256;
      var node = document.querySelector("#lab-proof code");
      if (node) node.textContent = card.proof_sha256;
    }).catch(function () {
      ui.proof = "hash unavailable in this browser";
    });
  }

  function apply(action, args) {
    var result = act(rules, state, action, args);
    if (!result.ok) {
      ui.note = ERROR_TEXT[result.error] || result.error;
      render();
      return;
    }
    state = result.state;
    state.live_verified = false;
    ui.note = describe(result.event);
    if (state.over) fileScore();
    remember();
    render();
    refreshProof();
  }

  function start(seed, difficulty) {
    state = newRun(rules, seed, difficulty);
    ui.note = "Run open. Seed " + seed + " on " + difficulty + ". Same seed replays the same draws.";
    ui.proof = "";
    if (!rules.collections[ui.collection]) ui.collection = Object.keys(rules.collections)[0];
    remember();
    render();
    refreshProof();
  }

  function todayUtc() {
    var now = new Date();
    var month = String(now.getUTCMonth() + 1).padStart(2, "0");
    var day = String(now.getUTCDate()).padStart(2, "0");
    return now.getUTCFullYear() + "-" + month + "-" + day;
  }

  function bind() {
    var lab = document.getElementById("lab");
    lab.addEventListener("click", function (event) {
      var actButton = event.target.closest("[data-act]");
      if (actButton && !actButton.disabled) {
        var action = actButton.getAttribute("data-act");
        if (action === "focus") apply("focus", { collection: ui.collection });
        else if (action === "forge") apply("forge", { collection: ui.collection, trait: ui.trait });
        else apply(action);
        return;
      }
      var traitButton = event.target.closest("[data-trait]");
      if (traitButton) {
        ui.collection = traitButton.getAttribute("data-collection");
        ui.trait = traitButton.getAttribute("data-trait");
        ui.note = ui.trait + " selected. Forge cost is dust, not energy, and it spends a turn.";
        render();
        return;
      }
      var focusButton = event.target.closest("[data-focus]");
      if (focusButton) {
        ui.collection = focusButton.getAttribute("data-focus");
        apply("focus", { collection: ui.collection });
        return;
      }
      if (event.target.id === "lab-clear-board") {
        writeJson(BOARD_KEY, []);
        ui.note = "Local board cleared on this browser.";
        render();
      }
    });

    document.getElementById("lab-start").addEventListener("click", function () {
      var seed = parseInt(document.getElementById("lab-seed").value, 10);
      var difficulty = document.getElementById("lab-difficulty").value;
      ui.name = document.getElementById("lab-name").value;
      try {
        start(seed, difficulty);
      } catch (exc) {
        ui.note = isGameError(exc) ? (ERROR_TEXT[exc.code] || exc.message) : "Could not open a run.";
        render();
      }
    });

    document.getElementById("lab-daily").addEventListener("click", function () {
      var day = todayUtc();
      document.getElementById("lab-seed").value = String(dailySeed(day));
      ui.note = "Daily seed for " + day + " UTC. It is public and shared by the calendar, not by a server.";
      render();
    });

    document.addEventListener("keydown", function (event) {
      if (!state || event.metaKey || event.ctrlKey || event.altKey) return;
      var tag = (event.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      var key = event.key.toLowerCase();
      var map = { d: "draw", r: "risk_draw", f: "arm_shield", m: "mulligan", u: "undo", enter: "finish" };
      if (key === "enter") {
        event.preventDefault();
        apply("finish");
      } else if (map[key]) {
        event.preventDefault();
        apply(map[key]);
      }
    });
  }

  function boot() {
    var lab = document.getElementById("lab");
    if (!lab) return;
    var script = document.currentScript;
    var rulesUrl = script ? new URL("trait_game_rules.json", script.src) : "trait_game_rules.json";
    fetch(rulesUrl).then(function (response) {
      if (!response.ok) throw new Error("rules");
      return response.json();
    }).then(function (loaded) {
      rules = loaded;
      if (rules.game_id !== GAME_ID) throw new Error("game_id");
      var saved = readJson(RUN_KEY, null);
      if (saved && saved.state && saved.state.version === rules.version && saved.state.game_id === GAME_ID) {
        state = saved.state;
        state.live_verified = false;
        if (saved.ui) {
          ui.collection = saved.ui.collection || ui.collection;
          ui.trait = saved.ui.trait || "";
          ui.name = saved.ui.name || ui.name;
        }
        var seedInput = document.getElementById("lab-seed");
        var diffInput = document.getElementById("lab-difficulty");
        var nameInput = document.getElementById("lab-name");
        if (seedInput) seedInput.value = String(state.seed);
        if (diffInput) diffInput.value = state.difficulty;
        if (nameInput && ui.name) nameInput.value = ui.name;
        ui.note = "Restored the run stored in this browser.";
        bind();
        render();
        refreshProof();
        return;
      }
      bind();
      start(dailySeed(todayUtc()), "lab");
      document.getElementById("lab-seed").value = String(state.seed);
    }).catch(function () {
      var banner = document.getElementById("lab-banner");
      if (banner) banner.textContent = "Rules failed to load. Serve this page with trait_game_rules.json beside it.";
    });
  }

  global.TraitLab = {
    GAME_ID: GAME_ID,
    LCG_MULT: LCG_MULT,
    dailySeed: dailySeed,
    newRun: newRun,
    act: act,
    bagWeights: bagWeights,
    proofBody: proofBody,
    canonical: canonical,
    rankBoard: rankBoard,
    gradeOf: gradeOf,
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
}(window));
