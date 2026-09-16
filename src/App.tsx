import { BrainMap } from '@/components/BrainMap';
import { WorkspacePanel } from '@/components/WorkspacePanel';
import { MemoryRail } from '@/components/MemoryRail';
import { ScanControls } from '@/components/ScanControls';
import { useMeshSocket } from '@/hooks/useMeshSocket';
import { useMeshStore } from '@/store/meshStore';

export default function App() {
  const { startScan, stopScan, focusNode, openWorkspace } = useMeshSocket();
  const scanning = useMeshStore((s) => s.scanning);
  const cycleCount = useMeshStore((s) => s.cycleCount);
  const lastCycleAt = useMeshStore((s) => s.lastCycleAt);
  const connected = useMeshStore((s) => s.connected);

  return (
    <div className="app-atmosphere">
      <header className="hero">
        <div className="hero-copy">
          <p className="brand">Personal Assistant</p>
          <h1 className="headline">Neural mesh for continuous system health</h1>
          <p className="lede">
            Watch workspaces light up as the brain scans architecture, vulns, drift,
            and improvements in one living map.
          </p>
          <div className="hero-cta">
            <ScanControls
              scanning={scanning}
              cycleCount={cycleCount}
              lastCycleAt={lastCycleAt}
              connected={connected}
              onStart={() => startScan()}
              onStop={() => stopScan()}
            />
            <span
              className={`connection-dot${connected ? ' online' : ''}`}
              title={connected ? 'Connected' : 'Reconnecting'}
              aria-hidden
            />
            <span className="connection-label">
              {connected ? 'Live mesh' : 'Connecting…'}
            </span>
          </div>
        </div>

        <BrainMap onFocusNode={(id) => focusNode(id)} />
      </header>

      <div className="detail-grid">
        <WorkspacePanel onOpenWorkspace={(id) => openWorkspace(id)} />
        <MemoryRail />
      </div>
    </div>
  );
}
