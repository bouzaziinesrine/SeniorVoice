import React, { useState, useRef, useEffect } from 'react';
import '../App.css'; // On remonte d'un niveau pour trouver App.css

const SeniorVoiceApp = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState('Appuyez pour parler');
  const [messages, setMessages] = useState([]); 
  
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);
  const chatEndRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
      setStatus("Veuillez autoriser le microphone.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && isRecording) {
      mediaRecorder.current.stop();
      setIsRecording(false);
      setStatus('Analyse en cours...');
    }
  };

  const playVoiceResponse = async (textToSay) => {
    try {
      const response = await fetch('https://seniorvoice-backend.onrender.com/text-to-speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: textToSay }),
      });
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
    } catch (err) {
      console.error("Erreur voix:", err);
    }
  };

  const sendToBackend = async (blob) => {
    const formData = new FormData();
    formData.append('file', blob, 'audio.wav');

    try {
      const response = await fetch('https://seniorvoice-backend.onrender.com/process-voice', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      const parsed = JSON.parse(data.ai_interpretation);
      
      setMessages(prevMessages => [
        ...prevMessages,
        { role: 'user', text: parsed.corrected_text || data.raw_text }, 
        { role: 'ai', text: parsed.reply, intent: parsed.intent }
      ]);
      
      setStatus('Prêt pour la prochaine requête');
      playVoiceResponse(parsed.reply);

    } catch (error) {
      setStatus("Oups, problème de connexion.");
    }
  };

  return (
    <div className="modern-container">
      <div className="glass-panel">
        <h1 className="title">SeniorVoice</h1>
        <p className="status">{status}</p>

        <div className="mic-wrapper">
          <button 
            className={`mic-btn ${isRecording ? 'recording' : ''}`}
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onTouchStart={startRecording}
            onTouchEnd={stopRecording}
          >
            🎤
          </button>
        </div>

        <div className="chat-section">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.role}`}>
              <span className="avatar">{msg.role === 'user' ? '👴' : '✨'}</span>
              <div className="bubble">
                {msg.role === 'ai' && <span className="intent-badge">{msg.intent}</span>}
                {msg.role === 'ai' && <br/>}
                {msg.text}
              </div>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

      </div>
    </div>
  );
};

export default SeniorVoiceApp;