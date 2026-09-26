// Sound Synthesizer using Web Audio API (100% Client-Side & Free)
class SoundManager {
  constructor() {
    this.ctx = null;
    this.isPlaying = false;
    this.currentLoop = null;
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

  // Plays a sharp, loud alert chime / horn for parking alerts
  playAlertSound() {
    this.init();
    if (!this.ctx) return;

    const playBeep = (freq, startTime, duration) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(freq, startTime);

      gain.gain.setValueAtTime(0.3, startTime);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(startTime);
      osc.stop(startTime + duration);
    };

    const now = this.ctx.currentTime;
    playBeep(880, now, 0.18);
    playBeep(1100, now + 0.12, 0.22);
    playBeep(1320, now + 0.26, 0.35);
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
      osc1.frequency.setValueAtTime(440, now); // A4
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(480, now); // Standard US/UK ring frequency

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(0.25, now + 0.05);
      gain.gain.setValueAtTime(0.25, now + 1.2);
      gain.gain.linearRampToValueAtTime(0.001, now + 1.3);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(this.ctx.destination);

      osc1.start(now);
      osc2.start(now);
      osc1.stop(now + 1.3);
      osc2.stop(now + 1.3);

      this.currentLoop = setTimeout(() => {
        ringCycle();
      }, 2500);
    };

    ringCycle();
  }

  stopRingtone() {
    this.isPlaying = false;
    if (this.currentLoop) {
      clearTimeout(this.currentLoop);
      this.currentLoop = null;
    }
  }
}

window.soundManager = new SoundManager();
