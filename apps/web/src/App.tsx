import React from 'react';

export default function App() {
  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1>OmniResearch</h1>
      <p>Autonomous Multimodal AI/ML Research Agent</p>
      <div style={{ background: '#f4f4f5', padding: '1rem', borderRadius: '8px' }}>
        <h3>System Status</h3>
        <ul>
          <li><strong>T00 Bootstrap:</strong> Complete</li>
          <li><strong>T01 Contracts & Core:</strong> Complete</li>
          <li><strong>T02 Database & Outbox:</strong> Complete</li>
        </ul>
      </div>
    </div>
  );
}
