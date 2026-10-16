# ACK Voice Studio: the guide

This guide is for the person making a voice, and for whoever is helping. It starts where the two installation guides end: the tool is installed and the Voice Studio window opens. If it is not installed yet, use the installation guide for your computer first: `ACK_Voice_Studio_Installation_Guide.MD` for Windows, `ACK_Voice_Studio_Installation_Guide_Ubuntu.MD` for Ubuntu.

It uses everyday words. A few words have a special meaning here (a *round*, a *training set*, a *voice file*); section 7 explains each one.

---

## 1. What it does, and what it does not

**What it does.** You bring in recordings of one person speaking. The computer writes down what it hears and cuts the recordings into pieces. It then trains a voice from them, a little at a time, in *rounds* of about 25 minutes. After each round you listen and decide: keep going, go back, or stop. When you are happy it makes one zip file. You copy that file to the phone and import it into ACK (AUDIO ARCHITECT, then CUSTOM VOICE, then IMPORT), and ACK speaks in that voice.

**Where your work stays.** Everything is kept in the folder `ack-voice-studio` in your home folder, on this computer. The recordings, the text written from them, the training and the finished voice are never uploaded, and there is no account. The tool downloads only programs, models and the starting voice, and it asks before each download.

**What it does not do.**

- It is not a medical or therapy tool, and it does not replace an assessment by a speech-language pathologist. ACK is a personal tool, shared as it is.
- It cannot promise a good voice. A voice sounds like its recordings: a quiet room, the same microphone and the same distance each time help more than anything else.
- It is not finished. Section 8 says what has been tried and what has not.

---

## 2. Before you start

**Whose voice is it?** The first thing the tool asks when you make a project is whose voice it is.

- **Your own.** Nothing more is asked.
- **Someone else's.** The tool needs a short note before it goes on: who agreed, what they agreed to, when, how they can take that back, and how they said yes (in speech, in writing, through a guardian, using an AAC device, or another way). The note is kept with the project. It is not a legal form. It is there so that nobody records a voice the person did not agree to. The person can say no, or stop, at any time, and then you delete their project (section 5 says how).

**How much to record.** The project form asks how many hours of recording you expect. The plan needs at least half an hour, and an hour or more is what the older guide aimed for. The screens then show how far you are, for example `About 20 of 60 minutes of speech you can use so far.`, and they never stop you for being under it. More recording, with more different sentences, helps: `Every minute helps the voice sound steadier.` How much is enough has not been measured here, so use your ears: the rounds in section 4 tell you.

**What the computer needs.** The installation guide has the table. In short: a graphics card from Nvidia with 8 GB of its own memory to train a voice, and about 25 GB of free room. Without such a card you can still bring in recordings, let the computer listen to them and make training sets, and then train on another computer.

---

## 3. Recording the voice

Bring in recordings you already have, or make new ones. Three ways are built in, and you choose each time.

**With the ACK app on the phone (the usual way).** In ACK, open AUDIO ARCHITECT and find CUSTOM VOICE, then RECORD TRAINING DATA. The phone checks that the room is quiet, shows sentences to read, cuts the speech into pieces by itself and lets you mark a piece that was not right. When you have enough, save everything to one file. You choose where it goes, and nothing is sent anywhere. Then copy that file to this computer yourself (a cable or a memory stick). **The phone also has a free-speech mode that records anyone who is nearby.** Use it only when everyone in the room has agreed.

**With audio files you already have.** A folder of audio files, each with a text file that says what is spoken, or a folder of audio files with one table, or audio files alone (the computer writes the words down). The tool never changes your files; it copies what it needs.

**With the older recorder, Freeform Studio.** Recordings made with it by hand can be brought in the same way. The window does not start it for you yet.

Whichever you use, the helper's job is the same: a quiet room, the microphone in the same place, and a person who is comfortable and can stop whenever they want. The one-page handout `VOICE_STUDIO_HELPER_HANDOUT.md` is made for the helper.

---

## 4. The path, one step at a time

Open the window, or use the terminal commands next to each step. Everything that changes something shows you what it will do and asks first. Anything you leave out of a command is asked one question at a time.

The terminal commands are written as the installation guides write them, with `PYTHONPATH=~/ack-tools/tools` in front. The word after `voice_studio.` names the tool, and `help` after it lists what it can do.

| | Step | In the window | In a terminal only |
|---|---|---|---|
| 1 | Make a project | Projects, `New project…` | |
| 2 | Bring in the recordings | Recordings, `Bring in recordings…` | |
| 3 | Get the listening model (once) | Recordings, `Get the listening model…` | |
| 4 | Let the computer listen | Recordings, `Let the computer listen…` | |
| 5 | Make a training set | Recordings, `Make a training set…` | |
| 6 | Get a starting voice | | `voices get` |
| 7 | Train a round | Training rounds, `Start a round…` | |
| 8 | Hear it and decide | Training rounds, `Choose this round` or `Go back to round…` | `voicefile listen` to hear it |
| 9 | Make the voice file | Voice file, `Make the voice file…` | |
| 10 | Put it on the phone | Voice file, `Show the folder` | |

### Step 1. Make a project

A project is one person's voice, with its own folder. Choose `New project…` on the Projects page, or:

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects new --own --name "Anna"
```

Use `--own` for your own voice. Leave it out and the tool asks whose voice it is, and for the note in section 2.

### Steps 2 to 5. From recordings to a training set

Bring in the recordings, then let the computer listen, then make the set. The first time only, get the listening model (about 485 MB); nothing else downloads it.

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings import ~/anna-package.zip --kind package --project anna
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings model
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings finish --project anna
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings set --project anna
```

`recordings show --project anna` tells you where you are and what to do next. It changes nothing. Letting the computer listen can take a while, and it carries on by itself if you close the window.

A *training set* is the recordings cut into pieces, each with the words spoken. The tool leaves out pieces that are too quiet, too noisy or cut inside a word, and says why. It never deletes a recording.

### Step 6. Get a starting voice

The computer trains your voice from a voice that already speaks, not from nothing. Two starting voices are offered. Whether you may use one is for you to decide. The tool shows you where it comes from and its licence, asks you to confirm that you read that, keeps your answer, and hosts none of them. It asks again before it downloads about 846 MB. This step is typed for now, because the window has no screen for it yet:

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voices get mike --project anna
```

### Step 7. Train a round

`Start a round…` shows the plan and asks first. A round is about 25 minutes. It stops by itself and saves what it has. You can close the window; the round carries on. To stop one early, use `Stop the round that is training`, or:

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds start --set dataset-1 --project anna
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds stop --project anna
```

Each round starts from the round you chose last, so the voice improves a little each time. The first round starts from the starting voice.

### Step 8. Hear it, then decide

After each round, listen. The computer says three sentences in the new voice: *Hello, my name is Anna. I need some help, please. Thank you, that is all.* It also writes down what it heard in each sound, as a hint and never a verdict.

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile listen --project anna --round 1
```

Then choose one of three things.

- **It sounds better than before.** Choose that round, and start another from it.
- **It sounds worse.** Go back to the round before it, and start from there.
- **You are happy.** Go to step 9.

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds list --project anna
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds choose 2 --project anna
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds back --project anna
```

Nothing is deleted when you choose or go back. There is no fixed number of rounds. The developer's own test used three. Stop when another round does not sound better to you.

### Steps 9 and 10. Make the voice file and put it on the phone

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile make --project anna
```

This makes one zip file, from the round you chose, in a new folder. Press `Show the folder` to open it. Copy the zip file to the phone. In ACK open AUDIO ARCHITECT, find CUSTOM VOICE, press IMPORT, and pick the file. ACK restarts by itself, and then you can choose MY VOICE as the voice profile.

---

## 5. Looking after your work

You do not need any of this on the first day. It is here so that you know it exists.

**Back up.** A backup is one file with the recordings, the notes and the finished voices of one project, written to a folder you choose, outside the project. The tool reads it back to check it, never replaces an earlier backup, and says if the folder looks like one a cloud service copies. It is not encrypted. Keep it somewhere you trust. The tool reminds you before a round and after recordings come in.

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup now --project anna --to ~/anna-backups
```

**Free up room.** A round leaves large files behind. `Free up space` in the window, or `rounds free`, shows what could go, with sizes, and removes only what you pick. The files that matter are never offered.

**Put a project away, or delete it.** `Put away…` hides a project and removes nothing. `Delete…` removes it for good: it lists what goes, names the backup first, and asks twice. Deleting is also how a person takes their voice back.

**Move the working files to another drive.** If the disk is full, `python3 -m voice_studio.scratch move` copies a project's working files to another place, checks every file, and only then switches. It never touches a recording.

**Update.** `python3 -m voice_studio.update check` asks github.com which releases of ACK Voice Studio exist, after it tells you what it will ask and you say yes. `get` fetches one into a new folder beside the old one. It never replaces the copy you are using, and it never runs by itself.

**Refresh and uninstall.** If something has broken, `python3 -m voice_studio.refresh check` looks and says what; `repair` mends it. `python3 -m voice_studio.uninstall show` lists what an uninstall would remove, and `remove` removes the programs and downloads. Neither touches a project, a recording, a backup or a starting voice.

---

## 6. When something goes wrong

1. **Run the same command again.** It carries on from where it stopped and does not repeat what is done.
2. **Read the three sentences.** A failure says what happened, whether anything was changed, and what to do next.
3. **Make a problem report if a helper is going to look.** A command that fails ends with two lines about it. The report is a text file with the versions, the checks on this computer and what went wrong. Your names and folders are blanked, and it holds no recordings, no text you made and no phrases. You see all of it first, and it is saved only where you say.

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report show
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report save --to ~/problem-report.txt
```

The tool never sends the report. Read it, and give the file to the helper yourself. The installation guide has a table of the messages you may meet while installing.

---

## 7. Words used here

- **Project.** One person's voice, with its own folder, notes and agreement.
- **Recordings.** The person speaking. They are kept as they were.
- **Listening model.** A program that writes down the words in a recording. It stays on this computer.
- **Training set.** The recordings cut into pieces, each with the words spoken. The voice is trained from this.
- **Starting voice.** A voice that already speaks, which yours is trained from.
- **Round.** One run of training, about 25 minutes.
- **Chosen round.** The round the next one starts from.
- **Voice file.** The one zip file you copy to the phone.
- **Working files.** The large files training leaves behind. They can be made again.

---

## 8. What has been tried

The tool was built and tested on a computer without a screen or a graphics card. What that cannot show was tried by the developer on one computer: Ubuntu 22.04 and 24.04 running inside Windows (WSL2), with an Nvidia RTX 4060. On it the setup, training, stopping and carrying on, the export and the packing of the voice file were run. Three training rounds were run from the terminal. The finished zip file was imported into ACK on a phone, and the window opened and worked. Most of the rest has **not** been run on a real computer yet: the backup, refresh, uninstall, move, update and problem report commands, hearing the voice through a speaker, and the Windows installer. A normal Ubuntu desktop on its own hardware has not been tried either. The file `VOICE_STUDIO_DEVICE_TEST.md` lists every check, and `VOICE_STUDIO_IT_GUIDE.md` says in section 11 what is tested and what is not. If you meet a sentence that is hard to follow, or something that fails, please tell the developer. That is how the tool improves.

The older step-by-step guides, `VOICE_TRAINING_GUIDE.md` and `VOICE_DATA_WSL_GUIDE.md`, are still there as the manual route. They do the same work by typing commands one by one.
