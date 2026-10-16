# ACK Voice Studio: a page for the helper

You are helping someone make a voice for ACK. It is their voice, so they decide. Print this page or keep it open. The long version is `VOICE_STUDIO_GUIDE.md`.

## Before you start

- **Ask first, and ask again.** They can say no, stop at any time, and take the voice back later. If the voice is not yours, the tool asks you for a short note: who agreed, to what, when, how they can take it back, and how they said yes.
- **Pick a quiet room.** Shut the door and switch off fans and televisions. Keep the microphone in the same place, the same distance from the mouth, every time.
- **Keep it short and kind.** Rest, drink water, and stop when they are tired. Nothing already kept is lost.
- **Charge the phone.** The phone needs about 300 MB of free room to start recording.

## While recording on the phone

- In ACK open AUDIO ARCHITECT, then CUSTOM VOICE, then RECORD TRAINING DATA.
- Let the phone check the room first. If it says the room is loud, find a quieter one.
- Read each sentence in the person's own voice. If a piece was not right, mark it. Do not correct them harshly.
- The recording screen makes no sound and no buzz, on purpose, so that nothing gets onto the recording.
- **Free speech records everyone nearby.** Use it only when everyone in the room has agreed.

## After the session

1. Save everything to one file on the phone. You choose where it goes. Nothing is sent.
2. Copy that file to the computer yourself, with a cable or a memory stick. Keep it out of shared or cloud folders.
3. Open Voice Studio. On Recordings press `Bring in recordings…` and say it is an ACK package.
4. Press `Let the computer listen…`, then `Make a training set…`.
5. Press `Start a round…`. A round takes about 25 minutes. After it, listen and choose: better, or go back.
6. When the voice is right, press `Make the voice file…`, copy the zip file to the phone, and import it in ACK.

## Looking after it

- Make a backup now and then: `python3 -m voice_studio.backup now`. Keep it somewhere you trust. It is not encrypted.
- If a command fails, run it again first. If it still fails, make a problem report with `python3 -m voice_studio.report show`. Names and folders are blanked, you see all of it first, and the tool never sends it.
- **Never send recordings by chat or email.** Send only the problem report, and only if you have read it.

## Who decides

The person decides what the voice says and who uses it. If they ask you to delete their voice, delete the project (Projects, `Delete…`). It lists what goes and asks twice.
