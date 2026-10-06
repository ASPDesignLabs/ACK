# GIF import and restore: checking a failure leaves nothing behind and damages nothing (on a real phone)

Two fixes, both guarded by automated tests, neither run on a phone:

* A GIF **import** that fails after ACK has started copying the file (too big, not really a GIF, a write error) used to leave the
  half-copied file in the GIF folder, and used to create the typed category before it knew the import would work (sections A to C).
  Guarded by `GifImportCleanupTest`, which reads the source: the Android part cannot run on a computer without a phone.
* A GIF deck **restore** (IMPORT DECK (.ZIP)) used to write each picture straight onto the file of the same name, then delete it if it
  was not a real GIF. Restore merges by id, so that name is often a GIF already on the phone, and a bad picture in the backup could
  destroy the good one. Now the picture is written beside it, checked, and only then moved into place (section D). The replacing
  step is tested by running it on real files (`VerifiedFileReplaceTest`); the screens and the phone's file system are what is not.

**This list is the part that was never run.** Each line is *do this → expect that*.

Use a **debug build**, with sample GIFs only. Take your time; none of it is timed.

**A backup first is a good idea.** In the GIF deck, open **BACKUP → EXPORT DECK (.ZIP)** and save it somewhere you control. (EXPORT .JSON
does not hold GIF pictures; the deck's own `.zip` does.) Nothing below deletes a GIF you already have, but it is a cheap thing to have.

## Make the test files (on the computer, then copy to the phone)

```
# Starts with a real GIF signature and is about 22 MB, so it is the SIZE limit (20 MB) that refuses it, not the signature check.
printf 'GIF89a' > too-big.gif; head -c 22000000 /dev/zero >> too-big.gif

# Has a .gif name but is not a GIF (random bytes), so it is the SIGNATURE check that refuses it.
head -c 2000 /dev/urandom > not-a-gif.gif

adb push too-big.gif not-a-gif.gif /sdcard/Download/
```

You also need one ordinary small GIF on the phone.

## Look at what is stored (before and after each step below)

```
adb shell run-as com.example.besu ls -l files/gif_library > folder-before.txt
adb shell run-as com.example.besu cat shared_prefs/ack_gif_library.xml > prefs-before.txt
```

If `files/gif_library` does not exist yet, `ls` says so; that counts as "empty". After a step, run the same two commands into
`folder-after.txt` and `prefs-after.txt` and `diff` each pair. (The two file names are the only things this reads; no GIF is opened.)

## A. An oversized file leaves nothing behind

- [ ] In the GIF deck, tap **IMPORT**, pick `too-big.gif`, type the category **OVERSIZE TEST**, tap **IMPORT**. → A red line in the dialog says
  **GIF exceeds the 20 MB safety limit.** and the dialog stays open. (It may take a moment to copy 20 MB before it stops.)
- [ ] Run the two commands into `*-after.txt`. → `diff folder-before.txt folder-after.txt` shows **no difference**: no new `GIF_….gif`,
  and nothing of about 20 MB. `diff prefs-before.txt prefs-after.txt` shows **no difference**: no `OVERSIZE TEST` category was stored.
- [ ] **CANCEL** the dialog. → The deck looks as it did. No category named **OVERSIZE TEST** anywhere.
- [ ] Close ACK completely and open it again, then repeat the two commands. → Still no difference.

## B. A file that is not a GIF leaves nothing behind

- [ ] **IMPORT**, pick `not-a-gif.gif`, category **NOT A GIF TEST**, **IMPORT**. → The red line says **Selected file is not a valid GIF.** and the
  dialog stays open.
- [ ] The two commands again. → **No difference** in the folder listing; **no** `NOT A GIF TEST` in `prefs-after.txt`.

## C. A good import still works, with the same category rules (the control)

- [ ] **IMPORT** your ordinary GIF with the category typed as **reactions**. → It imports, the dialog closes, and the GIF appears under a
  category called **REACTIONS** (capitals). The folder listing gains **exactly one** new `GIF_….gif`, and `ack_gif_library.xml` gains the
  **REACTIONS** category and the entry.
- [ ] Import another GIF with the category **Reactions** (different capitals). → It goes into the **same** REACTIONS category, not a second one.
- [ ] Import a third with the category box **left empty**. → It appears under **UNCATEGORIZED**.
- [ ] **SHARE**, **DISPLAY FULL SCREEN** and **DELETE** on one of the new GIFs. → All behave as before; after DELETE the file is gone from the
  listing.

## D. A restore with a bad picture never damages a GIF you already have

You need a GIF deck with at least two GIFs in it. **The `.zip` you make in the first step is your backup: keep it until the end.**

- [ ] In that deck, **BACKUP → EXPORT DECK (.ZIP)** and save it as `deck-backup.zip`. Pull it to the computer, then make a damaged copy:

  ```
  mkdir work && cd work && unzip ../deck-backup.zip
  # pick ONE picture inside the deck's folders (not manifest.json) and overwrite it with random bytes, keeping its name:
  head -c 2000 /dev/urandom > "<deck folder>/<category folder>/<that picture>.gif"
  zip -r ../deck-damaged.zip .        # manifest.json must be at the top of the zip
  adb push ../deck-damaged.zip /sdcard/Download/
  ```
- [ ] Note what is stored (a fingerprint of every picture, no picture is opened):
  `adb shell run-as com.example.besu sh -c 'md5sum files/gif_library/*' > restore-before.txt`
- [ ] **BACKUP → IMPORT DECK (.ZIP)**, pick `deck-damaged.zip`, onto the **same phone and deck**. → A toast says **IMPORTED *N* GIFS, 1
  SKIPPED** (*N* is one fewer than the deck holds), then ACK restarts after about a second and a half.
- [ ] Open the deck. → **Every GIF is still there, including the one you damaged in the zip**, and it plays as the original picture,
  not blank.
- [ ] Run the same `md5sum` command into `restore-after.txt`. → `diff restore-before.txt restore-after.txt` shows **no difference**. And
  `adb shell run-as com.example.besu ls files/gif_library` shows **no file ending in `.restoring`**.
- [ ] (Optional) `adb logcat -d -s ACK_GIF_BACKUP`. → A line like `Skipping "<title>": "GIF_….gif" is not a valid GIF.`
- [ ] Now import the **undamaged** `deck-backup.zip` over the same deck. → **IMPORTED *N+1* GIFS** with nothing skipped, the deck looks the
  same, and the `md5sum` list is still unchanged (same pictures, same names).
- [ ] (Optional, the replace path) Repeat the zip steps but, instead of random bytes, copy a **different real GIF** over one picture
  (same name). Import it. → That entry now shows the **new** picture, the others are unchanged, and there is still no `.restoring` file.

## Clean up

- [ ] Delete the test GIFs you imported in C with the app's own DELETE, and remove the test files from the phone
  (`adb shell rm /sdcard/Download/too-big.gif /sdcard/Download/not-a-gif.gif /sdcard/Download/deck-damaged.zip`). Keep `deck-backup.zip`
  until you are happy, then delete it yourself.

## What to send back

For any line that did not match: the line, what you saw, and the `diff` output of the two listings (they name files and categories, never
picture contents).
