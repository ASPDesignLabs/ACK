# Working with your voice-training data from WSL

A copy-paste guide for inspecting, checking, splitting, and backing up the recordings and datasets behind your
Piper voice, all from a WSL terminal. Companion to [VOICE_TRAINING_GUIDE.md](VOICE_TRAINING_GUIDE.md), which
covers the pipeline itself (setup, training, export, importing into ACK).

**About the "Example output" blocks.** Every command below was actually executed, on Ubuntu with ffmpeg 6.1,
against a small mock dataset with the same folder layout as yours (Chrome-style `.webm` takes, a split dataset,
fake checkpoints). Your numbers and file names will differ; the *shape* of the output is what to compare. Paths
show `/home/you` where yours will show your username. Commands marked *not run here* need your GPU, Windows, or
network, so they have no sample output.

**Safety labels.** `[read-only]` never changes anything. `[writes files]` creates new files or folders.
`[moves files, reversible]` renames or relocates, and the undo is shown. Nothing here deletes your recordings.

**Verified against the source, not assumed:** the recorder's storage layout and progress rule
([`piper_recording_studio/__main__.py`](https://github.com/rhasspy/piper-recording-studio/blob/master/piper_recording_studio/__main__.py)),
and how training reads `metadata.csv`, trims silence, and caches
([`dataset.py`](https://github.com/OHF-Voice/piper1-gpl/blob/master/src/piper/train/vits/dataset.py),
[`utils.py`](https://github.com/OHF-Voice/piper1-gpl/blob/master/src/piper/train/vits/utils.py)).


## 1. Paste this first (once per terminal)

Every command below uses these variables and one helper function, so you never retype a path.
Paste the block into your WSL terminal. To make it permanent, paste it at the end of `~/.bashrc`
(`nano ~/.bashrc`, then `source ~/.bashrc`).


**Variables + duration helper**

```bash
export PS_HOME=~/piper-recording-studio        # the recorder (its own repo + venv)
export REC=$PS_HOME/output/en-US               # raw takes:  <group>/<id>.webm  +  <id>.txt
export PROMPTS=$PS_HOME/prompts                # what the recorder asks you to read
export DS=~/piper/my-dataset-split             # splitter output:  wav/  +  metadata.csv
export TRAIN=~/piper/my-training               # config.json, cache dirs, exported .onnx
export LOGS=~/piper1-gpl/lightning_logs        # training checkpoints (see section 9 if this is wrong)
export SPLIT=~/tools/split_long_takes.py       # the splitter script

# Length in seconds of any .wav/.webm. Reads packet timestamps, so it also works on
# Chrome-recorded .webm files, whose header has no duration (see note below).
dur() { ffprobe -v error -select_streams a:0 -show_entries packet=pts_time,duration_time \
          -of csv=p=0 "$1" < /dev/null | tail -n1 | awk -F, '{printf "%.2f\n", $1+$2}'; }

# metadata.csv contents with any Windows (CRLF) line endings stripped, so shell tools behave
csvrows() { tr -d '\r' < "$DS/metadata.csv"; }
```

**Why `dur` instead of the obvious `ffprobe -show_entries format=duration`?** Chrome's recorder writes `.webm`
files with no duration in the header, so the obvious command prints `N/A` for every one of your takes
(verified: it returns `N/A` on a Chrome-style file while `dur` returns the true length).

**Why `csvrows`?** Older copies of the splitter wrote `metadata.csv` with Windows (CRLF) line endings, because
Python's `csv.writer` defaults to them. Training is unaffected (its reader normalizes line endings; verified
against `dataset.py`'s exact `open()` call), but shell tools like `awk` and `cut` see a stray carriage return on
every line. The current splitter writes plain LF; `csvrows` makes the checks below work with either.


## 2. Where everything lives

The recorder never tracks progress in a database. A prompt counts as "done" if and only if
`output/<language code>/<prompt file name>/<id>.txt` exists, where `<id>` is the line number counting from 0
(so `0.txt` is line 1), or the value in the first tab-separated column if your prompt file has one. Audio is the raw browser recording (`.webm`,
Opus), not a `.wav`. The language dropdown's value is the *code* (`en-US`), so every prompts folder ending in `_en-US`
feeds one shared pool.


**Map of the recorder folder [read-only]**

```bash
find "$PS_HOME" -maxdepth 3 -not -path '*/.venv*' -not -path '*/.git*' | sort | sed "s|$HOME|~|"
```

Example output (mock data):

```text
~/piper-recording-studio
~/piper-recording-studio/output
~/piper-recording-studio/output/en-US
~/piper-recording-studio/output/en-US/01_grimdark_frontier
~/piper-recording-studio/output/en-US/02_space_opera
~/piper-recording-studio/output/en-US/03_reflective
~/piper-recording-studio/prompts
~/piper-recording-studio/prompts/Voice Marathon_en-US
~/piper-recording-studio/prompts/Voice Marathon_en-US/01_grimdark_frontier.txt
~/piper-recording-studio/prompts/Voice Marathon_en-US/02_space_opera.txt
~/piper-recording-studio/prompts/Voice Marathon_en-US/03_reflective.txt
```


If you use Freeform Studio's export, `~/piper-recording-studio/output/en-US/freeform/` also appears here: `<take>_<piece>.wav`
with a matching `.txt`, a `manifest.json` and a hidden `.presplit` marker. It shows up as one more line (`freeform`) under
*Takes per prompt file*, its clips count toward *Total recorded time*, and none of the checks below flags it. Clips it stops
exporting are moved to `output/_freeform/en-US/retired/`, outside this folder.


## 3. How much have I recorded?


**Takes per prompt file [read-only]**

```bash
for g in "$REC"/*/; do
  n_audio=$(find "$g" -maxdepth 1 \( -name '*.webm' -o -name '*.wav' \) | wc -l)
  n_txt=$(find "$g" -maxdepth 1 -name '*.txt' | wc -l)
  printf '%-24s audio=%-3s text=%-3s\n' "$(basename "$g")" "$n_audio" "$n_txt"
done
```

Example output (mock data):

```text
01_grimdark_frontier     audio=5   text=5
02_space_opera           audio=5   text=5
03_reflective            audio=2   text=2
```


**Total recorded time [read-only]**

```bash
find "$REC" -type f \( -name '*.webm' -o -name '*.wav' \) | sort | while read -r f; do
  echo "$(dur "$f") $f"
done | awk '{s+=$1; n++} END {printf "%d takes, %.1f min total, %.1f s average\n", n, s/60, s/n}'
```

Example output (mock data):

```text
12 takes, 1.5 min total, 7.3 s average
```


**Progress against each prompt file [read-only]**

```bash
for p in "$PROMPTS"/*/*.txt; do
  g=$(basename "$p" .txt)
  total=$(grep -c '' "$p")
  done_n=$(find "$REC/$g" -maxdepth 1 -name '*.txt' 2>/dev/null | wc -l)
  printf '%-24s %2s / %2s recorded\n' "$g" "$done_n" "$total"
done
```

Example output (mock data):

```text
01_grimdark_frontier      5 /  5 recorded
02_space_opera            5 /  5 recorded
03_reflective             2 /  4 recorded
```


## 4. Look at one take


**Text, format, and length [read-only]**

```bash
G=01_grimdark_frontier; ID=0
cat "$REC/$G/$ID.txt"; echo
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels -of default=nw=1 "$REC/$G/$ID.webm"
echo "duration: $(dur "$REC/$G/$ID.webm") s"
```

Example output (mock data):

```text
Sample prompt sentence number 0 for group 01_grimdark_frontier. It has a second sentence too.
codec_name=opus
sample_rate=48000
channels=1
duration: 13.51 s
```


**Listen to it [read-only, needs WSLg audio or Windows]**

```bash
G=01_grimdark_frontier; ID=0        # which take to play

# Option A: play inside WSL (works if WSLg audio is set up; press q to quit)
ffplay -nodisp -autoexit "$REC/$G/$ID.webm"

# Option B: copy to Windows and open with your default player (always works)
cp "$REC/$G/$ID.webm" /mnt/c/Users/<you>/Desktop/ && explorer.exe "$(wslpath -w /mnt/c/Users/<you>/Desktop)"
```

*Not run here (needs your machine), so no sample output.*


## 5. Find problems before they reach training

The mock data has two problems planted on purpose (one audio file with no text, one text file with no audio)
so you can see what a hit looks like. **No output means no problems.**


**Audio with no text, or text with no audio [read-only]**

```bash
{
  find "$REC" -type f \( -name '*.webm' -o -name '*.wav' \) | while read -r f; do
    [ -f "${f%.*}.txt" ] || echo "AUDIO WITHOUT TEXT: $f"
  done
  find "$REC" -type f -name '*.txt' | while read -r t; do
    b="${t%.txt}"; [ -f "$b.webm" ] || [ -f "$b.wav" ] || echo "TEXT WITHOUT AUDIO: $t"
  done
} | sed "s|$HOME|~|"
```

Example output (mock data):

```text
AUDIO WITHOUT TEXT: ~/piper-recording-studio/output/en-US/02_space_opera/8.webm
TEXT WITHOUT AUDIO: ~/piper-recording-studio/output/en-US/02_space_opera/9.txt
```

The splitter silently skips both kinds (it only takes audio that has a matching `.txt`), so a typo here just means missing data.


**Empty or whitespace-only text files [read-only]**

```bash
find "$REC" -type f -name '*.txt' -exec grep -L '[^[:space:]]' {} +
```

Example output (mock data): *(nothing printed, which is the passing result)*


**Takes that are too short or too long [read-only]**

```bash
LO=1.0; HI=13     # seconds. Use HI=25 for real checking; 13 here just so the mock has hits.
find "$REC" -type f \( -name '*.webm' -o -name '*.wav' \) | sort | while read -r f; do
  echo "$(dur "$f") $f"
done | awk -v lo=$LO -v hi=$HI '$1<lo || $1>hi {print "OUT OF RANGE:", $0}' | sed "s|$HOME|~|"
```

Example output (mock data):

```text
OUT OF RANGE: 13.51 ~/piper-recording-studio/output/en-US/01_grimdark_frontier/0.webm
OUT OF RANGE: 14.01 ~/piper-recording-studio/output/en-US/01_grimdark_frontier/3.webm
```


**Loudest takes (clipping check) [read-only]**

```bash
find "$REC" -type f -name '*.webm' | sort | while read -r f; do
  v=$(ffmpeg -nostdin -i "$f" -af volumedetect -f null - 2>&1 | grep -E 'max_volume|mean_volume' | awk '{print $(NF-1)}' | tr '\n' ' ')
  echo "$v $f"
done | sort -k2 -n -r | head -5 | sed "s|$HOME|~|"
```

Example output (mock data):

```text
-16.7 -7.1  ~/piper-recording-studio/output/en-US/03_reflective/1.webm
-16.7 -7.1  ~/piper-recording-studio/output/en-US/02_space_opera/1.webm
-15.1 -7.1  ~/piper-recording-studio/output/en-US/01_grimdark_frontier/1.webm
-16.7 -7.3  ~/piper-recording-studio/output/en-US/01_grimdark_frontier/4.webm
-15.6 -7.3  ~/piper-recording-studio/output/en-US/02_space_opera/4.webm
```

Columns are `mean_volume max_volume` in dB. A `max_volume` of about `-1.0` or higher means the take clipped;
a `mean_volume` below about `-35` means it is very quiet.


## 6. Split long takes into training-sized sentences

Details and the reason for splitting are in [VOICE_TRAINING_GUIDE.md](VOICE_TRAINING_GUIDE.md). These are the moving parts.


**Update the splitter script from GitHub [writes file]**

```bash
mkdir -p ~/tools
curl -o "$SPLIT" https://raw.githubusercontent.com/aspdesignlabs/ack/claude/quirky-carson-ia01h1/tools/split_long_takes.py
```

*Not run here (needs your machine), so no sample output.*


**Dry run: report only, writes nothing [read-only]**

```bash
python3 "$SPLIT" --input-dir "$REC" --output-dir "$DS" --dry-run
```

Example output (mock data):

```text
SPLIT        0.webm                                         13.5s -> 2 sentences
PASSTHROUGH  1.webm                                         9.5s (single sentence)
PASSTHROUGH  2.webm                                         7.0s (single sentence)
MISMATCH     3.webm                                         2 sentence(s) vs 4 detected segment(s) -- sent to needs_review/
PASSTHROUGH  4.webm                                         4.5s (single sentence)
PASSTHROUGH  0.webm                                         4.5s (single sentence)
PASSTHROUGH  1.webm                                         4.5s (single sentence)
PASSTHROUGH  2.webm                                         9.5s (single sentence)
PASSTHROUGH  3.webm                                         4.5s (single sentence)
PASSTHROUGH  4.webm                                         7.0s (single sentence)
PASSTHROUGH  0.webm                                         4.5s (single sentence)
PASSTHROUGH  1.webm                                         4.5s (single sentence)

1 take(s) split, 10 short take(s) passed through, 1 take(s) need manual review (dry run -- nothing written)
Review the files in /home/you/piper/my-dataset-split/needs_review, then re-run with adjusted --min-silence-len/--silence-thresh, or split those specific ones by hand.
```

`PASSTHROUGH` = short take copied as-is. `SPLIT` = long take cut into one clip per sentence.
`MISMATCH` = number of detected pauses didn't equal number of sentences, so it goes to `needs_review/`.


**Real run, tuned [writes files; moves any old output aside first]**

```bash
[ -d "$DS" ] && mv "$DS" "$DS.old-$(date +%Y%m%d-%H%M%S)"     # never overwrite in place
python3 "$SPLIT" --input-dir "$REC" --output-dir "$DS" --min-silence-len 700 --silence-thresh -45
```

Example output (mock data):

```text
SPLIT        0.webm                                         13.5s -> 2 sentences
PASSTHROUGH  1.webm                                         9.5s (single sentence)
PASSTHROUGH  2.webm                                         7.0s (single sentence)
MISMATCH     3.webm                                         2 sentence(s) vs 4 detected segment(s) -- sent to needs_review/
PASSTHROUGH  4.webm                                         4.5s (single sentence)
PASSTHROUGH  0.webm                                         4.5s (single sentence)
PASSTHROUGH  1.webm                                         4.5s (single sentence)
PASSTHROUGH  2.webm                                         9.5s (single sentence)
PASSTHROUGH  3.webm                                         4.5s (single sentence)
PASSTHROUGH  4.webm                                         7.0s (single sentence)
PASSTHROUGH  0.webm                                         4.5s (single sentence)
PASSTHROUGH  1.webm                                         4.5s (single sentence)

Wrote 12 utterances to /home/you/piper/my-dataset-split/metadata.csv

1 take(s) split, 10 short take(s) passed through, 1 take(s) need manual review
Review the files in /home/you/piper/my-dataset-split/needs_review, then re-run with adjusted --min-silence-len/--silence-thresh, or split those specific ones by hand.
```

`--min-silence-len 700 --silence-thresh -45` are the values suggested earlier for over-splitting. Use whatever
gave you the best match count in the dry run. Moving the old output aside matters: the splitter never deletes, so
re-running into the same folder leaves stale `.wav` files behind that no longer appear in `metadata.csv`.


**What landed where [read-only]**

```bash
echo "training clips:  $(ls "$DS/wav" | wc -l)"
echo "needs review:    $(ls "$DS/needs_review"/*.txt 2>/dev/null | wc -l) take(s)"
echo; echo "first rows of metadata.csv:"; csvrows | head -n 4
```

Example output (mock data):

```text
training clips:  12
needs review:    1 take(s)

first rows of metadata.csv:
01_grimdark_frontier_0_00.wav|Sample prompt sentence number 0 for group 01_grimdark_frontier.
01_grimdark_frontier_0_01.wav|It has a second sentence too.
01_grimdark_frontier_1.wav|Sample prompt sentence number 1 for group 01_grimdark_frontier. It has a second sentence too.
01_grimdark_frontier_2.wav|Sample prompt sentence number 2 for group 01_grimdark_frontier. It has a second sentence too.
```


## 7. Check the dataset before you train on it

Run all of these after every split. **No output from a check means it passed.** The mock dataset has one bad row
planted on purpose (its wav file doesn't exist, it has no closing punctuation, and it contains a curly apostrophe
and em dashes) so you can see what hits look like.


**Rows vs files [read-only]**

```bash
echo "metadata rows: $(wc -l < "$DS/metadata.csv")    wav files: $(ls "$DS/wav" | wc -l)"
echo "-- rows pointing at a missing wav:"
csvrows | cut -d'|' -f1 | while read -r n; do [ -f "$DS/wav/$n" ] || echo "MISSING: $n"; done
echo "-- wavs not listed in metadata.csv:"
comm -13 <(csvrows | cut -d'|' -f1 | sort) <(ls "$DS/wav" | sort)
```

Example output (mock data):

```text
metadata rows: 13    wav files: 12
-- rows pointing at a missing wav:
MISSING: 01_grimdark_frontier_9.wav
-- wavs not listed in metadata.csv:
```


**Audio format: expect one line, pcm_s16le / 22050 / 1 [read-only]**

```bash
for f in "$DS"/wav/*.wav; do
  ffprobe -v error -show_entries stream=codec_name,sample_rate,channels -of csv=p=0 "$f" < /dev/null
done | sort | uniq -c
```

Example output (mock data):

```text
     12 pcm_s16le,22050,1
```


**Length spread [read-only]**

```bash
for f in "$DS"/wav/*.wav; do dur "$f"; done | sort -n | awk '{a[NR]=$1; s+=$1}
  END {printf "clips=%d  shortest=%.2fs  median=%.2fs  longest=%.2fs  total=%.1f min\n", NR, a[1], a[int((NR+1)/2)], a[NR], s/60}'
```

Example output (mock data):

```text
clips=12  shortest=4.50s  median=4.50s  longest=9.50s  total=1.2 min
```

Aim for clips between roughly 1 and 12 seconds. Anything much longer is what strains an 8 GB card.


**Text problems [read-only]**

```bash
echo "-- lines that don't end in . ! or ? (with optional closing quote):"
csvrows | awk -F'|' '$2 !~ /[.!?]["'"'"'”’]?$/ {print $1": "$2}'
echo "-- non-ASCII characters used in the text (count, character):"
csvrows | cut -d'|' -f2 | grep -o '[^ -~]' | sort | uniq -c | sort -rn
```

Example output (mock data):

```text
-- lines that don't end in . ! or ? (with optional closing quote):
01_grimdark_frontier_9.wav: The archivist said — quietly — that memory isn’t storage
-- non-ASCII characters used in the text (count, character):
      2 —
      1 ’
```

Non-ASCII characters (curly quotes, em dashes) are not errors, but they are the first place to look if a phrase is
mispronounced.


## 8. Back up first, and move things aside instead of deleting

Recordings are the one thing you cannot regenerate. Make a dated archive before any bulk change, and verify it.


**Dated backup of recordings + dataset, then verify it [writes file]**

```bash
mkdir -p ~/backups
STAMP=$(date +%Y%m%d-%H%M%S)
tar czf ~/backups/voice-data-$STAMP.tar.gz -C ~ piper-recording-studio/output piper/my-dataset-split
echo "files in archive: $(tar tzf ~/backups/voice-data-$STAMP.tar.gz | wc -l)"
ls -lh ~/backups | awk 'NR>1 {print $5, $9}' | sed "s/$STAMP/<timestamp>/"
```

Example output (mock data):

```text
files in archive: 49
2.1M voice-data-<timestamp>.tar.gz
```


**Copy the archive out of WSL too [writes file]**

```bash
mkdir -p /mnt/c/Users/<you>/voice-backups
cp ~/backups/voice-data-*.tar.gz /mnt/c/Users/<you>/voice-backups/
```

*Not run here (needs your machine), so no sample output.*

A backup that lives only inside WSL is one `wsl --unregister` or disk problem away from gone. Keep at least one
copy on the Windows side, and ideally one off the machine.

**Don't put it in a folder that syncs to the cloud.** Windows often takes over `Documents`, `Desktop` and `Pictures` with
OneDrive, so a copy there can be uploaded without you doing anything, and these are recordings of a voice. A folder directly
under `C:\Users\<you>` (like `voice-backups` above) is not usually synced, but check that OneDrive, Dropbox or Google Drive
isn't set to watch it. Freeform Studio's start-up message and `python -m freeform_studio.doctor` warn when a backup or
recordings folder looks synced. See [DATA_SOVEREIGNTY.md](DATA_SOVEREIGNTY.md).


**Freeform Studio makes its own backups.** While its server runs it writes a checked `freeform-backup-en-US-<timestamp>.tar.gz`
into `~/backups/freeform-studio` every 6 hours, when something has changed (see its README, *Backups and safety*). That folder is
inside WSL too, so the same warning applies: start it with `FREEFORM_BACKUPS=/mnt/c/Users/<you>/freeform-backups` (or
`--backup-dir`; a folder that is not cloud-synced), or copy the newest file out now and then.

The `voice-data` archive above includes `output/_freeform`, whose decoded copies take about 350 MB per hour of recording (usually
several times the size of the raw audio). If it gets big, leave `_freeform` out of it and rely on Freeform Studio's own (smaller, checksummed) backup
for those recordings:

```bash
tar czf ~/backups/voice-data-$STAMP.tar.gz --exclude='piper-recording-studio/output/_freeform' -C ~ piper-recording-studio/output piper/my-dataset-split
```

*Not run here against your folders (needs your machine); the `--exclude` form was checked on a small stand-in tree.*


**Prove the backup restores (into a scratch folder) [writes files]**

```bash
mkdir -p /tmp/restore-test && tar xzf ~/backups/voice-data-*.tar.gz -C /tmp/restore-test
find /tmp/restore-test -type f | wc -l
rm -rf /tmp/restore-test
```

Example output (mock data):

```text
41
```


**Move a bad batch aside instead of deleting it [moves files, reversible]**

```bash
mkdir -p ~/piper-recording-studio/_discarded
mv "$REC/02_space_opera" ~/piper-recording-studio/_discarded/02_space_opera.$(date +%Y%m%d)
# undo:  mv ~/piper-recording-studio/_discarded/02_space_opera.<date> "$REC/02_space_opera"
```

*Not run here (needs your machine), so no sample output.*


## 9. Training runs, checkpoints, and the cache

Two facts, both read from the piper1-gpl source, that change how you should work:

- **The cache key is only the row number plus the first ~45 characters of the text**
  (`get_cache_id` in `utils.py`), and an existing cache entry is never re-read from your audio. If you re-trim or
  re-record a clip but its row and opening words stay the same, training silently keeps using the old cached audio.
  **After changing any audio, point `--data.cache_dir` at a new empty folder.**
- **Training already trims silence itself** (Silero VAD, keeping 0.25 s before and after speech), and resamples
  whatever audio it is given. Leading and trailing silence in your clips is not something you need to hand-trim.


**Which checkpoints do I have? [read-only]**

```bash
for v in $(ls -1d "$LOGS"/version_* | sort -V); do
  echo "$(basename "$v"): $(ls "$v/checkpoints" | tr '\n' ' ')"
done
LATEST="$(ls -1d "$LOGS"/version_* | sort -V | tail -n1)/checkpoints/last.ckpt"
echo; echo "latest: $LATEST"
```

Example output (mock data):

```text
version_0: epoch=100-step=100.ckpt last.ckpt
version_1: epoch=500-step=500.ckpt last.ckpt
version_5: epoch=2100-step=2100.ckpt last.ckpt

latest: /home/you/piper1-gpl/lightning_logs/version_5/checkpoints/last.ckpt
```


**Cache folders: size and entries [read-only]**

```bash
du -sh "$TRAIN"/cache* 2>/dev/null | sed "s|$HOME|~|"
echo "entries in cache-marathon: $(ls "$TRAIN/cache-marathon" | wc -l)"
```

Example output (mock data):

```text
160K	~/piper/my-training/cache-marathon
entries in cache-marathon: 39
```


**Start with a fresh cache after editing audio [moves files, reversible]**

```bash
mv "$TRAIN/cache-marathon" "$TRAIN/cache-marathon.old-$(date +%Y%m%d-%H%M%S)"
mkdir "$TRAIN/cache-marathon"
```

*Not run here (needs your machine), so no sample output.*


**Where is my lightning_logs, really? [read-only]**

```bash
find ~ -maxdepth 5 -type d -name lightning_logs 2>/dev/null | sed "s|$HOME|~|"
```

Example output (mock data):

```text
~/piper1-gpl/lightning_logs
```

If this lists more than one, you have more than one training tree (this has happened before). Trust the one
belonging to the `piper1-gpl` you actually run:
`python3 -c "import piper.train; print(piper.train.__file__)"` prints which copy your active venv imports.


**Is training running, and how much GPU is left? [read-only]**

```bash
pgrep -af 'piper.train' || echo "training is not running"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv
```

*Not run here (needs your machine), so no sample output.*

Output depends on your machine. Check this before starting anything else that uses the GPU.


## 10. Handy shortcuts


| I want to... | Run |
|---|---|
| See the last thing I recorded | `find "$REC" -name '*.txt' -printf '%T@ %p\n' \| sort -n \| tail -n3` |
| Count everything at a glance | `echo "$(find "$REC" -name '*.txt' \| wc -l) takes, $(ls "$DS/wav" 2>/dev/null \| wc -l) training clips"` |
| Free disk space | `df -h ~ \| tail -n1` |
| Open a folder in Windows Explorer | `explorer.exe .` |
| Stop a training run | `Ctrl+C` **once** in its terminal, then wait |
