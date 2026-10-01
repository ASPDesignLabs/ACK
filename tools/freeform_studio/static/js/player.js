// SPDX-License-Identifier: GPL-3.0-or-later
// Plays exactly the part of the take that a piece covers (the same audio that will end up in the training clip),
// and reports the playhead so the current word can be highlighted.
export class Player extends EventTarget {
  constructor(audio) {
    super();
    this.audio = audio;
    this.stopAt = null;
    this.raf = null;
    audio.addEventListener("pause", () => this._stopped());
    audio.addEventListener("ended", () => this._stopped());
    audio.addEventListener("error", () => this.dispatchEvent(new Event("fail")));
    // animation frames stop in a background tab or with the screen off, so this keeps the end of a piece honest too
    audio.addEventListener("timeupdate", () => { if (this.stopAt !== null && audio.currentTime >= this.stopAt) audio.pause(); });
  }

  load(url) { this.audio.src = url; }
  get playing() { return !this.audio.paused; }
  get time() { return this.audio.currentTime; }

  async playRange(from, to) {
    const a = this.audio;
    if (a.readyState < 1) {
      await new Promise((resolve, reject) => {
        a.addEventListener("loadedmetadata", resolve, { once: true });
        a.addEventListener("error", () => reject(new Error("The audio could not be loaded.")), { once: true });
      });
    }
    this.stopAt = to;
    a.currentTime = Math.max(0, from);
    await a.play();
    this._loop();
  }

  stop() { this.audio.pause(); }

  _loop() {
    cancelAnimationFrame(this.raf);
    const tick = () => {
      if (this.audio.paused) return;
      const t = this.audio.currentTime;
      this.dispatchEvent(new CustomEvent("time", { detail: t }));
      if (this.stopAt !== null && t >= this.stopAt) { this.audio.pause(); return; }
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  _stopped() {
    // a "pause" from stopping the previous piece can arrive after the next one has already started: ignore it
    if (!this.audio.paused) return;
    cancelAnimationFrame(this.raf);
    this.stopAt = null;
    this.dispatchEvent(new Event("stopped"));
  }
}
