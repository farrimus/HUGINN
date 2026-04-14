// src/components/ErrorBoundary.tsx
//
// Catches unhandled errors in the React tree and shows a recovery screen
// instead of a blank page. The [ RESTART ] button clears the error state
// so React will re-render the subtree.

import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          background: '#000',
          color: '#c8a560',
          fontFamily: 'monospace',
          padding: '24px',
          minHeight: '100vh',
        }}>
          <p>HUGINN OFFLINE — CRITICAL FAULT</p>
          <p style={{ color: '#ff4444', marginTop: '8px' }}>
            {this.state.error.message}
          </p>
          <button
            onClick={() => this.setState({ error: null })}
            style={{
              marginTop: '16px',
              background: 'transparent',
              border: '1px solid #c8a560',
              color: '#c8a560',
              fontFamily: 'monospace',
              padding: '6px 12px',
              cursor: 'pointer',
            }}
          >
            [ RESTART ]
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
