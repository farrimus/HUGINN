import { StructureRouter } from './components/StructureRouter'
import { EntityProvider } from './context/EntityContext'
import { DashboardUI } from './components/DashboardUI'
import './styles/terminal.css'
import './styles/info-panel.css'
import './App.css'

// Game client injects this RPC bridge before page load — absent in all regular browsers
const isInGame = typeof (window as unknown as { eveFrontierRpcRequest?: unknown }).eveFrontierRpcRequest === 'function';

export default function App() {
  if (!isInGame) {
    return <DashboardUI />;
  }
  return (
    <EntityProvider>
      <StructureRouter />
    </EntityProvider>
  );
}
