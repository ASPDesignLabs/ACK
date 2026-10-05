# GIF import: checking a failed import leaves nothing behind (on a real phone)

A GIF import that fails after ACK has started copying the file (too big, not really a GIF, a write error) used to leave the half-copied
file in the GIF folder, and used to create the typed category before it knew the import would work. Both are fixed in the code and
guarded by `GifImportCleanupTest` (it reads the source: the Android part cannot run on a computer without a phone). **This list is the
part that was never run.** Each line is *do this → expect that*.

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

## Clean up

- [ ] Delete the test GIFs you imported in C with the app's own DELETE, and remove the two test files from the phone
  (`adb shell rm /sdcard/Download/too-big.gif /sdcard/Download/not-a-gif.gif`). If you made the backup `.zip` only for this, keep it until
  you are happy, then delete it yourself.

## What to send back

For any line that did not match: the line, what you saw, and the `diff` output of the two listings (they name files and categories, never
picture contents).
