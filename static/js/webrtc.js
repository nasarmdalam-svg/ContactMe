// WebRTC Peer-to-Peer Voice Calling Engine (100% Free via STUN)
class VoiceCallClient {
  constructor(tagId, role, onStateChange, onRemoteAudio) {
    this.tagId = tagId;
    this.role = role; // 'caller' or 'owner'
    this.onStateChange = onStateChange || (() => {});
    this.onRemoteAudio = onRemoteAudio || (() => {});
    
    this.ws = null;
    this.pc = null;
    this.localStream = null;
    
    this.config = {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
      ]
    };
  }

  connectSignaling() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${this.tagId}/${this.role}`;
    
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log(`[Signaling] Connected as ${this.role}`);
      this.onStateChange('connected_signaling');
    };

    this.ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        console.log('[Signaling] Received:', msg.type);
        await this.handleSignalingMessage(msg);
      } catch (err) {
        console.error('[Signaling] Parse error:', err);
      }
    };

    this.ws.onclose = () => {
      console.log('[Signaling] Disconnected');
      this.onStateChange('disconnected_signaling');
    };
  }

  async handleSignalingMessage(msg) {
    switch (msg.type) {
      case 'incoming_call':
        if (this.role === 'owner') {
          this.onStateChange('incoming_call');
        }
        break;

      case 'call_accepted':
        if (this.role === 'caller') {
          this.onStateChange('call_accepted');
          await this.createOffer();
        }
        break;

      case 'call_rejected':
        this.cleanup();
        this.onStateChange('call_rejected');
        break;

      case 'call_ended':
        this.cleanup();
        this.onStateChange('call_ended');
        break;

      case 'webrtc_offer':
        if (this.role === 'owner') {
          await this.handleOffer(msg.sdp);
        }
        break;

      case 'webrtc_answer':
        if (this.role === 'caller') {
          await this.handleAnswer(msg.sdp);
        }
        break;

      case 'ice_candidate':
        if (this.pc && msg.candidate) {
          try {
            await this.pc.addIceCandidate(new RTCIceCandidate(msg.candidate));
          } catch (e) {
            console.error('Error adding ICE candidate:', e);
          }
        }
        break;
    }
  }

  async startCall() {
    this.onStateChange('calling');
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch (e) {
      alert('Microphone access is required for voice call: ' + e.message);
      this.onStateChange('error');
      return;
    }

    this.sendSignaling({ type: 'call_request' });
  }

  async acceptCall() {
    this.onStateChange('in_call');
    try {
      this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch (e) {
      alert('Microphone access is required for voice call: ' + e.message);
      this.rejectCall();
      return;
    }

    this.sendSignaling({ type: 'call_accepted' });
  }

  rejectCall() {
    this.sendSignaling({ type: 'call_rejected' });
    this.cleanup();
    this.onStateChange('idle');
  }

  endCall() {
    this.sendSignaling({ type: 'call_ended' });
    this.cleanup();
    this.onStateChange('idle');
  }

  setupPeerConnection() {
    this.pc = new RTCPeerConnection(this.config);

    if (this.localStream) {
      this.localStream.getTracks().forEach((track) => {
        this.pc.addTrack(track, this.localStream);
      });
    }

    this.pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.sendSignaling({
          type: 'ice_candidate',
          candidate: event.candidate
        });
      }
    };

    this.pc.ontrack = (event) => {
      console.log('[WebRTC] Remote audio track received');
      const remoteStream = event.streams[0];
      this.onRemoteAudio(remoteStream);
    };

    this.pc.onconnectionstatechange = () => {
      console.log('[WebRTC] Connection state:', this.pc.connectionState);
      if (this.pc.connectionState === 'connected') {
        this.onStateChange('in_call');
      } else if (['disconnected', 'failed', 'closed'].includes(this.pc.connectionState)) {
        this.cleanup();
        this.onStateChange('call_ended');
      }
    };
  }

  async createOffer() {
    this.setupPeerConnection();
    const offer = await this.pc.createOffer({
      offerToReceiveAudio: true
    });
    await this.pc.setLocalDescription(offer);

    this.sendSignaling({
      type: 'webrtc_offer',
      sdp: offer
    });
  }

  async handleOffer(sdp) {
    this.setupPeerConnection();
    await this.pc.setRemoteDescription(new RTCSessionDescription(sdp));
    const answer = await this.pc.createAnswer();
    await this.pc.setLocalDescription(answer);

    this.sendSignaling({
      type: 'webrtc_answer',
      sdp: answer
    });
  }

  async handleAnswer(sdp) {
    if (this.pc) {
      await this.pc.setRemoteDescription(new RTCSessionDescription(sdp));
    }
  }

  sendSignaling(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('Signaling socket not open');
    }
  }

  cleanup() {
    if (this.localStream) {
      this.localStream.getTracks().forEach(t => t.stop());
      this.localStream = null;
    }
    if (this.pc) {
      this.pc.close();
      this.pc = null;
    }
  }
}
