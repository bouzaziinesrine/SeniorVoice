import React, { useState, useRef, useEffect } from 'react';
import '../App.css'; // On remonte d'un niveau pour trouver App.css

const SeniorVoiceApp = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState('Prêt à vous aider');
  const [messages, setMessages] = useState([]); 
  const API_BASE_URL = "https://senior-voice-api.onrender.com";
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);
  const chatEndRef = useRef(null);

  // Scroll automatique vers le bas à chaque nouveau message
  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // --- LOGIQUE ENREGISTREMENT ---
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: { 
          noiseSuppression: true, 
          echoCancellation: true, 
          autoGainControl: true 
        } 
      });
      
      mediaRecorder.current = new MediaRecorder(stream);
      audioChunks.current = [];

      mediaRecorder.current.ondataavailable = (event) => {
        audioChunks.current.push(event.data);
      };

      mediaRecorder.current.onstop = async () => {
        const audioBlob = new Blob(audioChunks.current, { type: 'audio/wav' });
        sendToBackend(audioBlob);
      };

      mediaRecorder.current.start();
      setIsRecording(true);
      setStatus('Je vous écoute...');
    } catch (err) {
      console.error("Erreur micro:", err);
      setStatus("Veuillez autoriser le micro");
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && isRecording) {
      mediaRecorder.current.stop();
      setIsRecording(false);
      setStatus('Analyse en cours...');
    }
  };

  // --- LOGIQUE SYNTHÈSE VOCALE (TTS) ---
  const playVoiceResponse = async (textToSay) => {
  try {
    const response = await fetch(`${API_BASE_URL}/text-to-speech`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: textToSay }),
    });

    if (!response.ok) throw new Error("Erreur serveur TTS");

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const audio = new Audio(url);
    
    // On attend que l'audio soit chargé avant de jouer
    audio.oncanplaythrough = () => {
      audio.play().catch(e => console.error("Erreur autoplay:", e));
    };
  } catch (err) {
    console.error("Détails de l'erreur voix:", err);
  }
};

  // --- LOGIQUE BACKEND ---
  const sendToBackend = async (blob) => {
    const formData = new FormData();
    formData.append('file', blob, 'audio.wav');

    try {
      const response = await fetch('https://senior-voice-api.onrender.com/process-voice', {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();
      
      // On gère si ai_interpretation arrive en String ou en Objet
      const parsed = typeof data.ai_interpretation === 'string' 
                     ? JSON.parse(data.ai_interpretation) 
                     : data.ai_interpretation;

      // Ajout des messages à la liste
      setMessages(prev => [
        ...prev,
        { role: 'user', text: parsed.corrected_text || data.raw_text }, 
        { role: 'ai', text: parsed.reply, intent: parsed.intent }
      ]);
      
      setStatus('Prêt pour la suite');
      
      if (parsed.reply) {
        playVoiceResponse(parsed.reply);
      }

    } catch (error) {
      console.error("Erreur backend:", error);
      setStatus("Problème de connexion.");
    }
  };

  return (
    <div className="app-viewport">
      <div className="main-card">
        
        {/* Header avec Logo et Statut */}
        <header className="app-header">
          <div className="logo-section">
            <span className="logo-icon">🎙️</span>
            <h1 className="app-title">SeniorVoice</h1>
          </div>
          <div className={`status-pill ${isRecording ? 'recording' : ''}`}>
            {status}
          </div>
        </header>

        {/* Zone de Chat */}
        <main className="chat-container">
          {messages.length === 0 ? (
            <div className="welcome-screen">
              <div className="welcome-icon">👴✨</div>
              <h2>Asslema !</h2>
              <p>Maintenez le bouton en bas pour me parler.</p>
            </div>
          ) : (
            messages.map((msg, index) => (
              <div key={index} className={`chat-row ${msg.role}`}>
                <div className="message-wrapper">
                  <div className="message-bubble">
                    {msg.role === 'ai' && <span className="intent-badge">{msg.intent}</span>}
                    <p className="message-content">{msg.text}</p>
                  </div>
                  <span className="avatar-icon">
                    {msg.role === 'user' ? '👴' : '✨'}
                  </span>
                </div>
              </div>
            ))
          )}
          <div ref={chatEndRef} />
        </main>

        {/* Footer avec bouton et instructions */}
        <footer className="app-footer">
          <div className="instruction-box">
            <p>Maintenez appuyé pour parler</p>
            <small>Attendez 1 seconde avant de commencer</small>
          </div>
          
          <div className="mic-container">
            <button 
              className={`mic-button-lg ${isRecording ? 'active' : ''}`}
              onMouseDown={startRecording}
              onMouseUp={stopRecording}
              onTouchStart={startRecording}
              onTouchEnd={stopRecording}
            >
              <div className="pulse-effect"></div>
              <span className="mic-emoji">🎤</span>
            </button>
          </div>
        </footer>

      </div>
    </div>
  );
};

export default SeniorVoiceApp;