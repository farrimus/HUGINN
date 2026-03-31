import { StructureRouter } from './components/StructureRouter'
import { EntityProvider } from './context/EntityContext'
import './styles/terminal.css'
import './styles/info-panel.css'
import './App.css'

export default function App() {
  return (
    <EntityProvider>
      <StructureRouter />
    </EntityProvider>
  );
}
