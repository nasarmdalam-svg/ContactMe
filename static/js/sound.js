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

  // Plays the clean chime audio file (tit-tit-tit)
  playAlertSound() {
    // If inside the ParkBuzz Android app, the native app plays chime.wav natively!
    // NEVER play here to prevent duplicate or bizarre sounds.
    if (window.ParkBuzzApp) return;

    try {
      if (!this.audio) {
        this.audio = new Audio('/static/audio/chime.wav');
      }
      this.audio.currentTime = 0;
      this.audio.play().catch(e => console.log('Audio play error:', e));
    } catch(e) {}
  }

  stopAlarm() {
    if (this.audio) {
      try {
        this.audio.pause();
        this.audio.currentTime = 0;
      } catch(e) {}
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
