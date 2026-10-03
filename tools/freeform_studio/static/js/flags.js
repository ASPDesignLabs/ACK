// SPDX-License-Identifier: GPL-3.0-or-later
// Plain-language wording for the warnings the recognizer and the checks can attach to a piece.
export const FLAG_TEXT = {
  low_confidence: "shaky word", has_digits: "has numbers", too_short: "very short", too_long: "long",
  possible_hallucination: "may be wrong", bracket_tag: "has a [tag]", repetitive: "repetitive", empty: "empty",
  has_symbols: "has symbols", cuts_word: "cuts a word",
  no_speech: "no speech", clipped: "distorted", quiet: "very quiet", noisy: "background noise", cut_off: "speech touches the edge",
  reads_differently: "differs from the card", phone_stumble: "you marked a slip", phone_disagrees: "phone and PC disagree",
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
  no_speech: "Hardly any of this piece is louder than the room. If you did say something, it was too quiet to count; otherwise drop it.",
  clipped: "The recording hit the loudest level it can several times, which sounds harsh. Re-record it, or move further from the microphone.",
  quiet: "Too soft to be brought up to full level when the training clips are made. Re-record it closer to the microphone, or leave it out.",
  noisy: "Your voice is not much louder than the background noise here. Listen: if the noise is clearly audible, leave it out.",
  cut_off: "Speech was still going at the very start or end of what ACK recorded, so the first or last word may be missing. Listen to both ends.",
  reads_differently: "What was heard does not match the words on the card. Listen, then fix the text, or re-record it if you misread.",
  phone_stumble: "You marked this one on the phone as a slip. Listen before you approve it.",
  phone_disagrees: "The phone and this computer disagree about whether there is speech in this clip. Listen to it.",
};
