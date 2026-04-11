declare const __BUILD_TIME__: string;
export const BUILD_TIME: string = __BUILD_TIME__;

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient } from '@tanstack/react-query'
import { EveFrontierProvider } from '@evefrontier/dapp-kit'
import './index.css'
import App from './App.tsx'

try {
  const queryClient = new QueryClient()
  const root = document.getElementById('root')

  if (!root) {
    throw new Error('Root element not found')
  }

  console.log('[Main] Starting React app initialization')

  createRoot(root).render(
    <StrictMode>
      <EveFrontierProvider queryClient={queryClient}>
        <App />
      </EveFrontierProvider>
    </StrictMode>,
  )

  console.log('[Main] React app rendered successfully')
} catch (error) {
  console.error('[Main] Initialization error:', error)
  const errorDiv = document.getElementById('root')
  if (errorDiv) {
    const msg = error instanceof Error ? error.message : String(error)
    errorDiv.innerHTML = `
      <div style="background: #000; color: #c8a560; font-family: monospace; padding: 20px;">
        <h1>Error - React App Failed</h1>
        <p>${msg}</p>
        <p><small>Check console for full stack trace</small></p>
      </div>
    `
  }
}
