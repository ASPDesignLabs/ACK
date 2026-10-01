// SPDX-License-Identifier: GPL-3.0-or-later
// Offers spoken-form wordings for the things a voice can't be trained on as written: digits, symbols, abbreviations.
// It never decides: a number can be said several ways ("2026" is "twenty twenty-six" or "two thousand twenty-six"), so
// it lists the likely readings and the person picks the one they actually said. Pure, so it can be tested on its own.

const ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
  "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"];
const TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];
const SCALES = [[1e12, "trillion"], [1e9, "billion"], [1e6, "million"], [1e3, "thousand"]];
const MAX = 999999999999999;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/** 123 -> "one hundred twenty-three" (or "one hundred and twenty-three" with { and: true }). Whole numbers up to 999 trillion. */
export function cardinal(n, { and = false } = {}) {
  if (!Number.isInteger(n) || n < 0 || n > MAX) throw new RangeError("out of range");
  if (n < 20) return ONES[n];
  if (n < 100) return TENS[Math.floor(n / 10)] + (n % 10 ? `-${ONES[n % 10]}` : "");
  if (n < 1000) {
    const rest = n % 100;
    return `${ONES[Math.floor(n / 100)]} hundred${rest ? `${and ? " and " : " "}${cardinal(rest)}` : ""}`;
  }
  for (const [value, name] of SCALES) {
    if (n >= value) {
      const rest = n % value;
      return `${cardinal(Math.floor(n / value), { and })} ${name}${rest ? `${and && rest < 100 ? " and " : " "}${cardinal(rest, { and })}` : ""}`;
    }
  }
  throw new RangeError("unreachable");
}

const ORDINAL_IRREGULAR = { one: "first", two: "second", three: "third", five: "fifth", eight: "eighth", nine: "ninth", twelve: "twelfth" };
const ordinalWord = (w) => ORDINAL_IRREGULAR[w] || (w.endsWith("y") ? `${w.slice(0, -1)}ieth` : `${w}th`);

/** 21 -> "twenty-first" */
export function ordinal(n) {
  const words = cardinal(n);
  const cut = Math.max(words.lastIndexOf(" "), words.lastIndexOf("-")) + 1;
  return words.slice(0, cut) + ordinalWord(words.slice(cut));
}

const digitWords = (s, zero = "zero") => [...s].map((d) => (d === "0" ? zero : ONES[Number(d)])).join(" ");

/** Ways to say a year: 1984 -> "nineteen eighty-four", 2026 -> "twenty twenty-six" and "two thousand twenty-six". */
export function yearWords(y) {
  if (!Number.isInteger(y) || y < 1100 || y > 2099) return [];
  const hi = Math.floor(y / 100), lo = y % 100;
  if (y >= 2000 && y <= 2009) return [y === 2000 ? "two thousand" : `two thousand ${ONES[lo]}`, ...(y === 2000 ? [] : [`two thousand and ${ONES[lo]}`, `twenty oh ${ONES[lo]}`])];
  const split = lo === 0 ? `${cardinal(hi)} hundred` : lo < 10 ? `${cardinal(hi)} oh ${ONES[lo]}` : `${cardinal(hi)} ${cardinal(lo)}`;
  return y >= 2010 ? [split, `two thousand ${cardinal(lo)}`, `two thousand and ${cardinal(lo)}`] : [split];
}

const decimalWords = (text) => {
  const [whole, frac] = text.split(".");
  return `${whole ? `${cardinal(Number(whole))} ` : ""}point ${digitWords(frac)}`;
};

const CURRENCY = { "$": ["dollar", "dollars", "cent", "cents"], "£": ["pound", "pounds", "penny", "pence"], "€": ["euro", "euros", "cent", "cents"], "¥": ["yen", "yen", null, null] };
const UNITS = {
  kg: ["kilogram", "kilograms"], g: ["gram", "grams"], mg: ["milligram", "milligrams"], km: ["kilometer", "kilometers"],
  cm: ["centimeter", "centimeters"], mm: ["millimeter", "millimeters"], lb: ["pound", "pounds"], lbs: ["pound", "pounds"],
  oz: ["ounce", "ounces"], mph: ["mile per hour", "miles per hour"], kph: ["kilometer per hour", "kilometers per hour"],
  ft: ["foot", "feet"], gb: ["gigabyte", "gigabytes"], mb: ["megabyte", "megabytes"], kb: ["kilobyte", "kilobytes"],
  tb: ["terabyte", "terabytes"], hz: ["hertz", "hertz"], khz: ["kilohertz", "kilohertz"], mhz: ["megahertz", "megahertz"],
  ghz: ["gigahertz", "gigahertz"], "°c": ["degree Celsius", "degrees Celsius"], "°f": ["degree Fahrenheit", "degrees Fahrenheit"],
};
const SYMBOLS = {
  "&": ["and"], "@": ["at"], "#": ["number", "hashtag", "pound"], "%": ["percent"], "+": ["plus"], "=": ["equals", "equal to"],
  "/": ["slash", "or", "per"], "*": ["star", "asterisk"], "~": ["about", "tilde"], "<": ["less than"], ">": ["greater than"],
  "°": ["degrees"], $: ["dollars"], "÷": ["divided by"], "×": ["times"], _: ["underscore"], "^": ["caret"],
};
// dot: needs a trailing full stop to count (otherwise "st" or "co" could just be words); keep: the stop also ends the sentence
const ABBREVIATIONS = {
  dr: { say: ["Doctor", "Drive"] }, mr: { say: ["Mister"] }, mrs: { say: ["Missus"] }, ms: { say: ["Miz"] },
  mt: { say: ["Mount"], dot: true }, st: { say: ["Saint", "Street"], dot: true }, ave: { say: ["Avenue"], dot: true },
  rd: { say: ["Road"], dot: true }, blvd: { say: ["Boulevard"], dot: true }, jr: { say: ["Junior"], dot: true },
  sr: { say: ["Senior"], dot: true }, vs: { say: ["versus"], dot: true }, etc: { say: ["et cetera"], dot: true, keep: true },
  approx: { say: ["approximately"], dot: true }, dept: { say: ["department"], dot: true }, govt: { say: ["government"], dot: true },
  inc: { say: ["Incorporated"], dot: true }, ltd: { say: ["Limited"], dot: true }, co: { say: ["Company"], dot: true },
  "e.g": { say: ["for example"], dot: true }, "i.e": { say: ["that is"], dot: true },
};

const LINKISH = /@[^\s@]+\.[^\s@]+|:\/\/|^www\./i;   // email addresses and web addresses are left alone
const LEAD = /^["'“‘(\[]*/;
const TRAIL = /[)"'”’\]]*[.,;:!?…]*[)"'”’\]]*$/;

const plural = (n, [one, many]) => (n === 1 ? one : many);
const num = (s) => Number(s.replace(/,/g, ""));

function optionsForBody(body, trail) {
  const out = [];
  const add = (text, note) => { if (text !== null && text !== undefined) out.push({ text, note }); };
  let m;

  if ((m = body.match(/^([$£€¥])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?([kKmMbB])?$/))) {
    const [sym, whole, cents, mag] = [m[1], num(m[2]), m[3], m[4]];
    const [one, many, cOne, cMany] = CURRENCY[sym];
    if (mag) {
      const scale = { k: "thousand", m: "million", b: "billion" }[mag.toLowerCase()];
      if (!cents) add(`${cardinal(whole)} ${scale} ${many}`, "amount");
    } else if (cents && cOne) {
      const c = Number(cents.padEnd(2, "0"));
      const amount = `${cardinal(whole)} ${plural(whole, [one, many])}`;
      if (c === 0) add(amount, "amount");
      else if (whole === 0) add(`${cardinal(c)} ${plural(c, [cOne, cMany])}`, "amount");
      else { add(`${amount} and ${cardinal(c)} ${plural(c, [cOne, cMany])}`, "amount"); add(`${amount} ${cardinal(c)}`, "short form"); }
    } else {
      add(`${cardinal(whole)} ${plural(whole, [one, many])}`, "amount");
    }
    return out;
  }
  if ((m = body.match(/^(\d+(?:\.\d+)?)%$/))) {
    add(`${m[1].includes(".") ? decimalWords(m[1]) : cardinal(Number(m[1]))} percent`, "percent");
    return out;
  }
  if ((m = body.match(/^(\d+)(st|nd|rd|th)$/i))) {
    if (Number(m[1]) <= MAX) add(ordinal(Number(m[1])), "ordinal");
    return out;
  }
  if ((m = body.match(/^(\d{1,2}):(\d{2})(?:\s?([ap])\.?m\.?)?$/i))) {
    const h = Number(m[1]), min = Number(m[2]), ap = m[3] && `${m[3].toLowerCase()} m`;
    if (h > 24 || min > 59) return out;
    const hour = cardinal(h);
    const clock = min === 0 ? (ap ? hour : `${hour} o'clock`) : min < 10 ? `${hour} oh ${cardinal(min)}` : `${hour} ${cardinal(min)}`;
    add(ap ? `${clock} ${ap}` : clock, "time");
    if (!ap && min === 30) add(`half past ${hour}`, "time");
    if (!ap && min === 15) add(`quarter past ${hour}`, "time");
    if (!ap && min === 45 && h < 24) add(`quarter to ${cardinal(h + 1)}`, "time");
    return out;
  }
  if ((m = body.match(/^(\d{1,2})\s?([ap])\.?m\.?$/i))) {
    if (Number(m[1]) >= 1 && Number(m[1]) <= 12) add(`${cardinal(Number(m[1]))} ${m[2].toLowerCase()} m`, "time");
    return out;
  }
  if ((m = body.match(/^(\d+)\/(\d+)$/))) {
    const [a, b] = [Number(m[1]), Number(m[2])];
    if (a > MAX || b > MAX) return out;
    const date = a >= 1 && a <= 12 && b >= 1 && b <= 31 ? `${MONTHS[a - 1]} ${ordinal(b)}` : null;
    const fraction = b === 2 ? (a === 1 ? "one half" : `${cardinal(a)} halves`)
      : b === 4 ? (a === 1 ? "one quarter" : `${cardinal(a)} quarters`)
        : b > 1 ? `${cardinal(a)} ${a === 1 ? ordinal(b) : `${ordinal(b)}s`}` : null;
    const fractionLikely = a < b && b <= 10;                 // thirds, quarters, tenths... but nobody says "twenty-fifths"
    if (fractionLikely) { add(fraction, "fraction"); add(date, "date"); } else { add(date, "date"); }
    add(`${cardinal(a)} ${cardinal(b)}`, "said as two numbers");
    add(`${cardinal(a)} over ${cardinal(b)}`, "said as a ratio");
    return out;
  }
  if ((m = body.match(/^(\d+)[-–—](\d+)$/))) {
    if (Number(m[1]) <= MAX && Number(m[2]) <= MAX) {
      add(`${cardinal(Number(m[1]))} to ${cardinal(Number(m[2]))}`, "range");
      add(`${cardinal(Number(m[1]))} through ${cardinal(Number(m[2]))}`, "range");
    }
    return out;
  }
  if ((m = body.match(/^(\d+(?:\.\d+)?)\s?([A-Za-z°]{1,4})$/)) && UNITS[m[2].toLowerCase()]) {
    const value = m[1];
    const unit = UNITS[m[2].toLowerCase()];
    const words = value.includes(".") ? decimalWords(value) : cardinal(Number(value));
    add(`${words} ${value === "1" ? unit[0] : unit[1]}`, "with its unit");
    return out;
  }
  if ((m = body.match(/^(\d*\.\d+)$/))) {
    add(decimalWords(m[1]), "decimal");
    if (/^\d+\./.test(m[1]) === false) add(`zero ${decimalWords(m[1])}`, "decimal");
    return out;
  }
  if ((m = body.match(/^(\d{1,3}(?:,\d{3})+|\d+)$/))) {
    const text = m[1];
    const n = num(text);
    if (n > MAX) { add(digitWords(text.replace(/,/g, "")), "digit by digit"); return out; }
    const plain = !text.includes(",");
    if (plain && text.length > 1 && text.startsWith("0")) { add(digitWords(text), "digit by digit"); add(digitWords(text, "oh"), "digit by digit"); return out; }
    const long = plain && text.length >= 5;
    if (long) add(digitWords(text), "digit by digit");
    if (plain && text.length === 4) for (const y of yearWords(n)) add(y, "as a year");
    add(cardinal(n), "as a number");
    if (n > 100 && !(n % 100 === 0 && n < 1000) && cardinal(n, { and: true }) !== cardinal(n)) add(cardinal(n, { and: true }), "as a number, with \"and\"");
    if (plain && text.length >= 3 && !long) add(digitWords(text), "digit by digit");
    return out;
  }
  if ((m = body.match(/^(\d+)([A-Za-z]{1,3})$/)) && !UNITS[m[2].toLowerCase()] && Number(m[1]) <= MAX) {
    add(`${cardinal(Number(m[1]))} ${m[2]}`, "number and letters");
    return out;
  }
  if ((m = body.match(/^#(\d+)$/))) {
    if (Number(m[1]) <= MAX) { add(`number ${cardinal(Number(m[1]))}`, "number sign"); add(`hashtag ${cardinal(Number(m[1]))}`, "hashtag"); }
    return out;
  }
  if (SYMBOLS[body]) {
    SYMBOLS[body].forEach((s) => add(s, "symbol"));
    return out;
  }
  const abbr = ABBREVIATIONS[body.toLowerCase()];
  if (abbr && (!abbr.dot ? true : trail.startsWith("."))) {
    abbr.say.forEach((s) => add(s, "abbreviation"));
    return out;
  }
  if (/^[A-Za-z]+(?:&[A-Za-z]+)+$/.test(body)) { add(body.replace(/&/g, " and "), "ampersand"); return out; }
  if (/^[A-Za-z]+(?:\/[A-Za-z]+)+$/.test(body)) {
    const parts = body.split("/");
    add(parts.join(parts.some((p) => /^(or|and)$/i.test(p)) ? " " : " or "), "slash");   // "and/or" is said "and or"
    add(parts.join(" slash "), "slash");
    return out;
  }
  return out;
}

/**
 * Wordings for one whitespace-separated token, as full replacements for it (its surrounding punctuation is kept).
 * Returns [] when the token needs nothing, e.g. an ordinary word, an email address or a web address.
 */
export function suggestSpoken(token) {
  if (!token || LINKISH.test(token)) return [];
  const lead = token.match(LEAD)[0];
  const rest = token.slice(lead.length);
  const trail = rest.match(TRAIL)[0];
  const body = rest.slice(0, rest.length - trail.length);
  if (!body) return [];
  const seen = new Set();
  const out = [];
  for (const o of optionsForBody(body, trail)) {
    const abbr = ABBREVIATIONS[body.toLowerCase()];
    const keptTrail = abbr && trail.startsWith(".") && !abbr.keep ? trail.slice(1) : trail;
    const text = `${lead}${o.text}${keptTrail}`;
    if (!seen.has(text)) { seen.add(text); out.push({ text, note: o.note }); }
    if (out.length === 4) break;
  }
  return out;
}

/** Every token of `text` that has spoken-form suggestions: [{ index, token, options }]. */
export function spokenTokens(text) {
  const out = [];
  text.split(/\s+/).filter(Boolean).forEach((token, index) => {
    const options = suggestSpoken(token);
    if (options.length) out.push({ index, token, options });
  });
  return out;
}

/** `text` with token number `index` replaced (an empty replacement removes it). Words are rejoined with single spaces. */
export function replaceToken(text, index, replacement) {
  const tokens = text.split(/\s+/).filter(Boolean);
  if (index < 0 || index >= tokens.length) return text;
  if (replacement) tokens[index] = replacement; else tokens.splice(index, 1);
  return tokens.join(" ");
}
