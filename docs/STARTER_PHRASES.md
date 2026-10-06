# Starter phrases: for review

**Status: DRAFT. Not yet reviewed by a speech-language pathologist (SLP).**

When ACK is installed on a phone for the first time, its buttons say nothing personal. They start with the plain, neutral
phrases below, grouped by what a message *does*: say yes, say no, ask for help, ask someone to repeat, hold the turn while typing,
say who you are, ask for a break, set a boundary. The person changes any of them whenever they like; they are only a starting point.

This page is for the developer and the SLP to read and change. The tables are the real thing: a test fails if this page and the app
ever disagree, so what you review here is exactly what a new install gets.

## Who gets these, and when

- **A new install only.** A phone that already has ACK keeps every phrase exactly as it is. Nothing is changed under anyone.
- **A new Matrix deck** made later on a phone that began with these phrases starts with the same twelve.
- **After DELETE DATA > MESSAGES AND DECKS**, the Matrix deck shows these twelve again (a wiped phone should not show the
  developer's own wording). The STARTERS deck below is not made again after a wipe, only on a brand-new install.
- **Restoring an older backup** onto a phone that has these: any starter phrase you have **not** edited goes back to what the old
  phone showed. Anything you edited is never touched. The restore confirmation says so.

## The sets

<!-- STARTER-TABLES:BEGIN (checked against core/StarterSets.kt; edit the code, not this block) -->
**The 12 Matrix gestures** (each gesture stays where it is; only the words are new)

| Pose | Gesture | Says | Kind |
|---|---|---|---|
| IDENTITY | thumbs up | Yes. | yes |
| IDENTITY | wave | Hello. | social |
| IDENTITY | ask name | Please say that again. | repair (ask to say it again) |
| IDENTITY | name | I am using a communication device. | name or ID |
| DEFEND | stop | Stop. | boundary |
| DEFEND | wait | Please wait, I am typing. | turn-holding (I'm typing) |
| DEFEND | break | I need a break. | break |
| DEFEND | leave alone | I need some space. | boundary |
| CONNECT | nice | No. | no |
| CONNECT | same | Thank you. | social |
| CONNECT | sorry | I need help. | help |
| CONNECT | meet | Nice to meet you. | social |

**The STARTERS Quick Actions deck** (3 groups of 4 buttons)

| Group | Button | Says | Kind |
|---|---|---|---|
| ANSWERS | YES | Yes. | yes |
| ANSWERS | NO | No. | no |
| ANSWERS | DON'T KNOW | I don't know. | not sure |
| ANSWERS | MAYBE | Maybe. | not sure |
| REPAIR | AGAIN | Please say that again. | repair (ask to say it again) |
| REPAIR | SLOWER | Please speak more slowly. | repair (ask to say it again) |
| REPAIR | DON'T UNDERSTAND | I don't understand. | repair (ask to say it again) |
| REPAIR | I'M TYPING | Please wait, I am typing. | turn-holding (I'm typing) |
| SOCIAL | HELLO | Hello. | social |
| SOCIAL | THANK YOU | Thank you. | social |
| SOCIAL | SORRY | Sorry. | social |
| SOCIAL | HELP | I need help. | help |
<!-- STARTER-TABLES:END -->

## What changed from before, and the trade-off to check

The twelve Matrix gestures are muscle memory, so none of them moved; only the words changed. Four of the old phrases read as the
developer's own or as tactical ("Systems Online.", "Identify yourself.", a personal handle, and "Leave me alone."), so they are gone.
"Greetings." and "Sorry." gave up their Matrix slots to make room for "No." and "I need help.", because twelve slots cannot hold
every kind of message. They are in the STARTERS deck instead, along with a second copy of "Please wait, I am typing."

## For the reviewer

Please mark up this page, or reply with changes. Questions that need an answer:

1. Is the wording clear and respectful for both adults and children? Is "I need some space." understood as meant?
2. "No." sits on the CONNECT / nice gesture and "I need help." on CONNECT / sorry. Are those good places for the two most
   important messages, or should some other gesture carry them?
3. Is any kind of message missing that a first-time user would need straight away (for example pain, the toilet, being hungry or
   thirsty)? Anything here that should be shorter, longer, or in simpler words?
4. Is a Quick Actions deck the right place for the second set, or would the SLP rather it were organised another way?

Reviewed by: ______________________  Date: ______________

## Changing the phrases

The data is in `app/src/main/java/com/example/besu/core/StarterSets.kt`. Edit it there and update the block between the two marker
lines above to match (the test prints what it expects). The text ACK falls back to for a button with no saved value
(`BASE_TEMPLATE` in `data/CommandRepository.kt`) is **never** edited, because an untouched button on an existing phone uses it; a test
pins it. New phrases are saved as values instead.
