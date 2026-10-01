// Plain-language wording for the warnings the recognizer and the checks can attach to a piece.
export const FLAG_TEXT = {
  low_confidence: "shaky word", has_digits: "has numbers", too_short: "very short", too_long: "long",
  possible_hallucination: "may be wrong", bracket_tag: "has a [tag]", repetitive: "repetitive", empty: "empty",
  has_symbols: "has symbols", cuts_word: "cuts a word",
};

export const FLAG_HELP = {
  low_confidence: "Some words were hard to hear (dotted underline). Listen, and fix any that are wrong.",
  has_digits: "Contains numbers. Spell them the way you said them, for example \"twenty twenty-six\". Suggestions are under the text box.",
  has_symbols: "Contains symbols such as & or %. Write them out as spoken words.",
  too_short: "Very short. Clips under a second are usually left out of training.",
  too_long: "Long. Clips over about 11 seconds are left out of training.",
  possible_hallucination: "The recognizer may have made this up. Listen before you trust it.",
  repetitive: "Looks repetitive. The recognizer may have got stuck, so check it against the audio.",
  bracket_tag: "Contains a [tag] or (note). Remove it unless you actually said it.",
  empty: "No words in this piece. Type what was said, or drop it.",
  cuts_word: "A cut point falls inside a word, so the audio and the text may not match. Move the cut point, or change the text.",
};
