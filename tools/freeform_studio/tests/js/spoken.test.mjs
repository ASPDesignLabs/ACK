import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const { cardinal, ordinal, yearWords, suggestSpoken, spokenTokens, replaceToken } = await load("spoken.js");
const say = (token) => suggestSpoken(token).map((o) => o.text);

// ---------------------------------------------------------------- the number words themselves
test("cardinals read the way people say them", () => {
  const cases = { 0: "zero", 7: "seven", 13: "thirteen", 20: "twenty", 21: "twenty-one", 99: "ninety-nine", 100: "one hundred",
    101: "one hundred one", 342: "three hundred forty-two", 1000: "one thousand", 1001: "one thousand one",
    12345: "twelve thousand three hundred forty-five", 1000000: "one million", 2500000: "two million five hundred thousand",
    1234567: "one million two hundred thirty-four thousand five hundred sixty-seven", 1000000000: "one billion" };
  for (const [n, words] of Object.entries(cases)) assert.equal(cardinal(Number(n)), words, n);
  assert.equal(cardinal(123, { and: true }), "one hundred and twenty-three");
  assert.equal(cardinal(1005, { and: true }), "one thousand and five");
  assert.throws(() => cardinal(-1));
  assert.throws(() => cardinal(1.5));
});

test("ordinals", () => {
  const cases = { 1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 8: "eighth", 9: "ninth", 11: "eleventh", 12: "twelfth",
    20: "twentieth", 21: "twenty-first", 22: "twenty-second", 30: "thirtieth", 100: "one hundredth", 101: "one hundred first", 1000: "one thousandth" };
  for (const [n, words] of Object.entries(cases)) assert.equal(ordinal(Number(n)), words, n);
});

test("years have the usual ways of being said", () => {
  assert.deepEqual(yearWords(1984), ["nineteen eighty-four"]);
  assert.deepEqual(yearWords(1905), ["nineteen oh five"]);
  assert.deepEqual(yearWords(1900), ["nineteen hundred"]);
  assert.deepEqual(yearWords(2026), ["twenty twenty-six", "two thousand twenty-six", "two thousand and twenty-six"]);
  assert.deepEqual(yearWords(2000), ["two thousand"]);
  assert.ok(yearWords(2005).includes("two thousand five") && yearWords(2005).includes("twenty oh five"));
  assert.deepEqual(yearWords(1066), []);   // not treated as a year
});

// ---------------------------------------------------------------- tokens
test("a plain number offers its readings, most likely first, and keeps surrounding punctuation", () => {
  assert.deepEqual(say("20"), ["twenty"]);
  assert.deepEqual(say("2026"), ["twenty twenty-six", "two thousand twenty-six", "two thousand and twenty-six", "two zero two six"]);
  assert.equal(say("1984,")[0], "nineteen eighty-four,");
  assert.equal(say('"42."')[0], '"forty-two."');
  assert.deepEqual(say("(5)"), ["(five)"]);
  assert.equal(say("1,234")[0], "one thousand two hundred thirty-four");
  assert.ok(say("123").includes("one hundred and twenty-three") && say("123").includes("one two three"));
  assert.equal(say("90210")[0], "nine zero two one zero");               // five digits without commas: probably a code
  assert.ok(say("90210").includes("ninety thousand two hundred ten"));
  assert.equal(say("007")[0], "zero zero seven");
  assert.ok(say("007").includes("oh oh seven"));
});

test("ordinals, percentages, decimals", () => {
  assert.deepEqual(say("3rd"), ["third"]);
  assert.deepEqual(say("21st,"), ["twenty-first,"]);
  assert.deepEqual(say("5%"), ["five percent"]);
  assert.deepEqual(say("12.5%"), ["twelve point five percent"]);
  assert.deepEqual(say("3.14"), ["three point one four"]);
  assert.deepEqual(say(".5"), ["point five", "zero point five"]);
});

test("money", () => {
  assert.deepEqual(say("$5"), ["five dollars"]);
  assert.deepEqual(say("$1"), ["one dollar"]);
  assert.deepEqual(say("$5.50"), ["five dollars and fifty cents", "five dollars fifty"]);
  assert.deepEqual(say("$0.99"), ["ninety-nine cents"]);
  assert.deepEqual(say("$1,200"), ["one thousand two hundred dollars"]);
  assert.deepEqual(say("$5k"), ["five thousand dollars"]);
  assert.deepEqual(say("£50"), ["fifty pounds"]);
  assert.deepEqual(say("€3.20"), ["three euros and twenty cents", "three euros twenty"]);
  assert.deepEqual(say("$5,"), ["five dollars,"]);
});

test("times, fractions, dates and ranges", () => {
  assert.deepEqual(say("10:30"), ["ten thirty", "half past ten"]);
  assert.deepEqual(say("3:05pm"), ["three oh five p m"]);
  assert.deepEqual(say("9:00"), ["nine o'clock"]);
  assert.deepEqual(say("5pm"), ["five p m"]);
  assert.deepEqual(say("1/2"), ["one half", "January second", "one two", "one over two"]);
  assert.deepEqual(say("3/4"), ["three quarters", "March fourth", "three four", "three over four"]);
  assert.equal(say("2/3")[0], "two thirds");
  assert.deepEqual(say("12/25"), ["December twenty-fifth", "twelve twenty-five", "twelve over twenty-five"]);   // not "twelve twenty-fifths"
  assert.ok(say("24/7").includes("twenty-four seven"));
  assert.deepEqual(say("5-10"), ["five to ten", "five through ten"]);
});

test("units, letters after numbers, and number signs", () => {
  assert.deepEqual(say("5km"), ["five kilometers"]);
  assert.deepEqual(say("1kg"), ["one kilogram"]);
  assert.deepEqual(say("2.5GB"), ["two point five gigabytes"]);
  assert.deepEqual(say("72°F"), ["seventy-two degrees Fahrenheit"]);
  assert.deepEqual(say("4K"), ["four K"]);
  assert.deepEqual(say("3D"), ["three D"]);
  assert.deepEqual(say("#5"), ["number five", "hashtag five"]);
});

test("symbols on their own, and inside words", () => {
  assert.deepEqual(say("&"), ["and"]);
  assert.deepEqual(say("%"), ["percent"]);
  assert.deepEqual(say("+"), ["plus"]);
  assert.deepEqual(say("="), ["equals", "equal to"]);
  assert.deepEqual(say("R&D"), ["R and D"]);
  assert.deepEqual(say("and/or"), ["and or", "and slash or"]);
  assert.deepEqual(say("&,"), ["and,"]);
});

test("abbreviations: titles always, others only with their full stop; the stop goes unless it ends the sentence", () => {
  assert.equal(say("Dr.")[0], "Doctor");
  assert.deepEqual(say("Dr."), ["Doctor", "Drive"]);
  assert.deepEqual(say("Mr."), ["Mister"]);
  assert.deepEqual(say("Mrs."), ["Missus"]);
  assert.deepEqual(say("Dr"), ["Doctor", "Drive"]);
  assert.deepEqual(say("St."), ["Saint", "Street"]);
  assert.deepEqual(say("St"), []);                 // without the stop it may just be a word
  assert.deepEqual(say("co"), []);
  assert.deepEqual(say("vs."), ["versus"]);
  assert.deepEqual(say("etc."), ["et cetera."]);   // that stop also ends the sentence, so it stays
  assert.deepEqual(say("e.g.,"), ["for example,"]);
  assert.deepEqual(say("i.e."), ["that is"]);
  assert.deepEqual(say("Dr.,"), ["Doctor,", "Drive,"]);
});

test("ordinary words, email and web addresses, and odd shapes need nothing", () => {
  for (const t of ["hello", "Hello,", "friend.", "don't", "state-of-the-art", "me@example.com", "https://example.com", "www.example.com", "", "...", "COVID-19", "a1b2"]) {
    assert.deepEqual(say(t), [], t);
  }
});

test("absurd or invalid numbers never throw", () => {
  for (const t of ["99999999999999999999", "25:99", "0/0", "13/45", "1e5", "5--5", "$", "$$5", "%%"]) assert.doesNotThrow(() => suggestSpoken(t), t);
  assert.ok(say("99999999999999999999")[0].startsWith("nine nine"));   // too big to say as one number: digit by digit
  assert.deepEqual(say("25:99"), []);
});

test("no more than four options per token and no duplicates", () => {
  for (const t of ["2026", "123", "1/2", "$5.50", "10:30", "St.", "007"]) {
    const o = say(t);
    assert.ok(o.length <= 4 && new Set(o).size === o.length, t);
  }
});

// ---------------------------------------------------------------- whole texts
test("tokens needing spoken forms are found by position, and replacing one rebuilds the text", () => {
  const text = "Dr. Smith paid $20 on May 3rd & left.";
  const found = spokenTokens(text);
  assert.deepEqual(found.map((f) => [f.index, f.token]), [[0, "Dr."], [3, "$20"], [6, "3rd"], [7, "&"]]);
  assert.equal(replaceToken(text, 3, "twenty dollars"), "Dr. Smith paid twenty dollars on May 3rd & left.");
  assert.equal(replaceToken("a b c", 1, ""), "a c");                     // an empty replacement removes the token
  assert.equal(replaceToken("a  b   c", 2, "see"), "a b see");            // spacing is tidied
  assert.equal(replaceToken("a b", 9, "x"), "a b");                       // out of range: unchanged
  assert.deepEqual(spokenTokens("nothing to fix here."), []);
});

test("after every number and symbol is replaced, nothing is left to flag", () => {
  let text = "I bought 3 apples for $2.50 at 10:30 & paid 5% tax.";
  for (let guard = 0; guard < 10; guard++) {
    const next = spokenTokens(text)[0];
    if (!next) break;
    text = replaceToken(text, next.index, next.options[0].text);
  }
  assert.equal(text, "I bought three apples for two dollars and fifty cents at ten thirty and paid five percent tax.");
  assert.ok(!/[\d&%$]/.test(text));
});
