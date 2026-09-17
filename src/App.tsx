import { BrainMap } from '@/components/BrainMap';
import { WorkspacePanel } from '@/components/WorkspacePanel';
import { MemoryRail } from '@/components/MemoryRail';
import { ScanControls } from '@/components/ScanControls';
import { SwiftGuidePanel } from '@/components/SwiftGuidePanel';
import { SuggestionsPanel } from '@/components/SuggestionsPanel';
import { useMeshSocket } from '@/hooks/useMeshSocket';
import { useMeshStore } from '@/store/meshStore';

export default function App() {
  const {
    startScan,
    stopScan,
    focusNode,
    openWorkspace,
    openConcept,
    guideStart,
    guideNext,
    guidePrev,
  } = useMeshSocket();
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
            Scan workspaces light the brain; Swift Guide diamonds walk concepts that
            mesh into those same regions. Suggestions surface concrete next implementations.
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
            <button type="button" className="btn" onClick={() => guideStart()}>
              Swift Guide tour
            </button>
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

      <div className="detail-grid three">
        <WorkspacePanel onOpenWorkspace={(id) => openWorkspace(id)} />
        <SwiftGuidePanel
          onOpenConcept={(id) => openConcept(id)}
          onGuideStart={() => guideStart()}
          onGuideNext={() => guideNext()}
          onGuidePrev={() => guidePrev()}
          onOpenWorkspace={(id) => openWorkspace(id)}
        />
        <MemoryRail />
      </div>

      <div className="detail-grid">
        <SuggestionsPanel
          onOpenWorkspace={(id) => openWorkspace(id)}
          onOpenConcept={(id) => openConcept(id)}
        />
      </div>
    </div>
  );
}
