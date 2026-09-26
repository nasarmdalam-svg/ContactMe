// Sound Synthesizer using Web Audio API (100% Client-Side & Free)
class SoundManager {
  constructor() {
    this.ctx = null;
    this.isPlaying = false;
    this.alarmLoop = null;
    this.ringLoop = null;
  }

  init() {
    if (!this.ctx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        this.ctx = new AudioContext();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  // Plays a repeating urgent car horn / alarm siren until stopped or after 8 cycles
  playAlertSound(repeat = 6) {
    this.init();
    if (!this.ctx) return;
    this.stopAlarm();

    let count = 0;
    const playHornCycle = () => {
      if (count >= repeat) {
        this.stopAlarm();
        return;
      }
      count++;

      const now = this.ctx.currentTime;
      const playBeep = (freq, offset, duration) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(freq, now + offset);

        gain.gain.setValueAtTime(0.35, now + offset);
        gain.gain.exponentialRampToValueAtTime(0.001, now + offset + duration);

        osc.connect(gain);
        gain.connect(this.ctx.destination);

        osc.start(now + offset);
        osc.stop(now + offset + duration);
      };

      // Urgent dual-tone car horn burst: HONK - HONK - HONK
      playBeep(850, 0.00, 0.22);
      playBeep(1100, 0.00, 0.22);

      playBeep(850, 0.28, 0.22);
      playBeep(1100, 0.28, 0.22);

      playBeep(950, 0.56, 0.35);
      playBeep(1200, 0.56, 0.35);

      this.alarmLoop = setTimeout(playHornCycle, 1400);
    };

    playHornCycle();
  }

  stopAlarm() {
    if (this.alarmLoop) {
      clearTimeout(this.alarmLoop);
      this.alarmLoop = null;
    }
  }

  // Starts a repeating ringing tone for incoming calls until stopped
  startRingtone() {
    this.init();
    if (!this.ctx || this.isPlaying) return;
    this.isPlaying = true;

    const ringCycle = () => {
      if (!this.isPlaying) return;
      const now = this.ctx.currentTime;

      // Two-pulse telephone ring
      const osc1 = this.ctx.createOscillator();
      const osc2 = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc1.type = 'sine';
      osc1.frequency.setValueAtTime(440, now);
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(480, now);

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(0.3, now + 0.05);
      gain.gain.setValueAtTime(0.3, now + 1.2);
      gain.gain.linearRampToValueAtTime(0.001, now + 1.3);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(this.ctx.destination);

      osc1.start(now);
      osc2.start(now);
      osc1.stop(now + 1.3);
      osc2.stop(now + 1.3);

      this.ringLoop = setTimeout(() => {
        ringCycle();
      }, 2400);
    };

    ringCycle();
  }

  stopRingtone() {
    this.isPlaying = false;
    if (this.ringLoop) {
      clearTimeout(this.ringLoop);
      this.ringLoop = null;
    }
  }
}

window.soundManager = new SoundManager();
