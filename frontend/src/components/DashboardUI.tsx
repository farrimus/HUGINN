import { useState, useRef, useEffect, useCallback } from 'react';
import { useConnection, abbreviateAddress } from '@evefrontier/dapp-kit';
import { useToolOutput } from '../hooks/useToolOutput';
import { useRelayStream } from '../hooks/useRelayStream';
import { InfoPanel } from './InfoPanel';
import '../styles/dashboard.css';

const MAX_EXCHANGES = 5;

const CLOSING_MESSAGE =
  'This relay carries no further transmissions. If you need to communicate, find a structure.';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

/**
 * Desktop dashboard — two-column layout.
 * Left: InfoPanel mirroring the in-game terminal with [REDACTED] values.
 * Right: Open relay chat with HUGINN (wallet required, 5 exchanges max).
 */
export function DashboardUI() {
  const { isConnected, walletAddress, handleConnect, hasEveVault } = useConnection();
  const { currentToolType, currentData, isAnimating, finishAnimation, setDirect } = useToolOutput();
  const { sendMessage } = useRelayStream();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingText, setStreamingText] = useState('');
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [exchangeCount, setExchangeCount] = useState(0);
  const [channelClosed, setChannelClosed] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Set hardcoded [REDACTED] baseline — all values absent since there's no structure
  useEffect(() => {
    setDirect('baseline', {
      crudVersion: 'HUGINN - Version',
      signature: '[REDACTED]',
      shellName: '[REDACTED]',
      accessLevel: 'NONE',
      assemblySignature: '[REDACTED]',
      location: '[REDACTED]',
    });
  }, [setDirect]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText]);

  // Focus input when wallet connects
  useEffect(() => {
    if (isConnected) {
      inputRef.current?.focus();
    }
  }, [isConnected]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || isStreaming || channelClosed || !isConnected) return;

    const userMessage = input.trim();
    setInput('');

    const newCount = exchangeCount + 1;
    setExchangeCount(newCount);

    const history = messages.map(m => ({ role: m.role, content: m.content }));
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsStreaming(true);
    setStreamingText('');

    let fullText = '';

    await sendMessage(
      {
        message: userMessage,
        history,
        owner_address: walletAddress || '',
      },
      {
        onTextChunk: (text) => {
          fullText += text;
          setStreamingText(fullText);
        },
        onDone: () => {
          setMessages(prev => [...prev, { role: 'assistant', content: fullText }]);
          setStreamingText('');
          setIsStreaming(false);

          if (newCount >= MAX_EXCHANGES) {
            setTimeout(() => {
              setMessages(prev => [...prev, { role: 'assistant', content: CLOSING_MESSAGE }]);
              setChannelClosed(true);
            }, 600);
          }
        },
        onError: (err) => {
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: `[RELAY LOST]: ${err.message}`,
          }]);
          setStreamingText('');
          setIsStreaming(false);
        },
      }
    );
  }, [input, isStreaming, channelClosed, isConnected, exchangeCount, messages, walletAddress, sendMessage]);

  const remaining = MAX_EXCHANGES - exchangeCount;

  return (
    <div className="dashboard-ui">

      {/* ── Left: terminal mirror with REDACTED state ── */}
      <div className="dashboard-left terminal-ui">
        <InfoPanel
          currentToolType={currentToolType}
          currentData={currentData}
          isAnimating={isAnimating}
          onAnimationEnd={finishAnimation}
          showSplash={false}
          activeNavItems={[]}
        />
        <span className="dashboard-no-anchor">NO STRUCTURE ANCHOR</span>
      </div>

      {/* ── Right: relay chat ── */}
      <div className="dashboard-right">
        <div className="dashboard-right-header">
          <span className="dashboard-header-label">&gt; RELAY</span>
          {isConnected && walletAddress && (
            <span className="dashboard-wallet">{abbreviateAddress(walletAddress)}</span>
          )}
        </div>

        {/* Wallet connect */}
        {!isConnected && (
          <div className="dashboard-connect-area">
            {hasEveVault ? (
              <button className="dashboard-connect-btn" onClick={handleConnect}>
                IDENTIFY PILOT
              </button>
            ) : (
              <div className="dashboard-no-wallet">
                <p>No wallet detected.</p>
                <p>Install the Eve Vault extension to establish identity.</p>
              </div>
            )}
          </div>
        )}

        {/* Messages */}
        <div className="dashboard-messages">
          {messages.length === 0 && isConnected && (
            <div className="dashboard-msg dashboard-msg-info">
              Relay established. No structure anchor present. Transmission range is limited.
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`dashboard-msg dashboard-msg-${msg.role === 'user' ? 'user' : 'assistant'}`}>
              {msg.role === 'user' ? `> ${msg.content}` : `[HUGINN]: ${msg.content}`}
            </div>
          ))}

          {streamingText && (
            <div className="dashboard-msg dashboard-msg-assistant">
              {`[HUGINN]: ${streamingText}`}<span className="dashboard-cursor">▊</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        {isConnected && !channelClosed && (
          <div className="dashboard-input-area">
            <span className="dashboard-prompt">&gt;</span>
            <input
              ref={inputRef}
              className="dashboard-input"
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleSend(); }}
              placeholder={`${remaining} transmission${remaining !== 1 ? 's' : ''} remaining`}
              disabled={isStreaming}
              autoComplete="off"
            />
          </div>
        )}

        {channelClosed && (
          <div className="dashboard-channel-closed">RELAY CLOSED</div>
        )}
      </div>
    </div>
  );
}
