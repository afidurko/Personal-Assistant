import { useCallback, useState } from 'react';
import { BrainMap } from '@/components/BrainMap';
import { CortexStage } from '@/components/CortexStage';
import { CamPresence } from '@/components/CamPresence';
import { WorkspacePanel } from '@/components/WorkspacePanel';
import { MemoryRail } from '@/components/MemoryRail';
import { ScanControls } from '@/components/ScanControls';
import { SwiftGuidePanel } from '@/components/SwiftGuidePanel';
import { SuggestionsPanel } from '@/components/SuggestionsPanel';
import { AgentSpawnBay } from '@/components/AgentSpawnBay';
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
    runAgentCycle,
    startIssueLoop,
    stopIssueLoop,
  } = useMeshSocket();
  const scanning = useMeshStore((s) => s.scanning);
  const cycleCount = useMeshStore((s) => s.cycleCount);
  const lastCycleAt = useMeshStore((s) => s.lastCycleAt);
  const connected = useMeshStore((s) => s.connected);
  const [listening, setListening] = useState(false);
  const [flatMap, setFlatMap] = useState(false);
  const onListeningChange = useCallback((v: boolean) => setListening(v), []);

  const onFocusArea = useCallback(
    (areaId: string) => {
      const nodes = useMeshStore.getState().nodes;
      const key = areaId.replace('area.', '');
      const hit =
        nodes.find((n) => n.id.includes(key)) ||
        nodes.find((n) => n.label.toLowerCase().includes(key));
      if (hit) focusNode(hit.id);
    },
    [focusNode],
  );

  return (
    <div className="app-atmosphere cam-home">
      <header className="hero cam-hero">
        <div className="hero-brand-row">
          <p className="brand">Cam</p>
          <span
            className={`connection-dot${connected ? ' online' : ''}`}
            title={connected ? 'Connected' : 'Reconnecting'}
            aria-hidden
          />
          <span className="connection-label">
            {connected ? 'Live mesh' : 'Connecting…'}
          </span>
        </div>
        <h1 className="headline">Glass cortex lit — she listens when you open the mic.</h1>
        <p className="lede">
          Speak and Cam answers. The near-clear brain stays live while she and her agents spawn
          improve work in the background.
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
          <button type="button" className="btn btn-ghost" onClick={() => guideStart()}>
            Swift Guide tour
          </button>
          <button
            type="button"
            className={`btn btn-ghost${flatMap ? ' active' : ''}`}
            onClick={() => setFlatMap((v) => !v)}
            aria-pressed={flatMap}
          >
            {flatMap ? '3D cortex' : '2D map'}
          </button>
        </div>

        <div className="hero-stage">
          {flatMap ? (
            <BrainMap onFocusNode={(id) => focusNode(id)} />
          ) : (
            <CortexStage listening={listening} onFocusArea={onFocusArea} />
          )}
          <CamPresence onListeningChange={onListeningChange} />
        </div>
      </header>

      <AgentSpawnBay
        onFocusNode={(id) => focusNode(id)}
        onRunAgentCycle={() => runAgentCycle()}
        onStartIssueLoop={() => startIssueLoop()}
        onStopIssueLoop={() => stopIssueLoop()}
      />

      <div className="detail-grid three">
        <WorkspacePanel onOpenWorkspace={(id) => openWorkspace(id)} />
        <SwiftGuidePanel
          onOpenConcept={(id) => openConcept(id)}
          onGuideStart={() => guideStart()}
          onGuideNext={() => guideNext()}
          onGuidePrev={() => guidePrev()}
          onOpenWorkspace={(id) => openWorkspace(id)}
        />
        <SuggestionsPanel
          onOpenWorkspace={(id) => openWorkspace(id)}
          onOpenConcept={(id) => openConcept(id)}
        />
      </div>

      <div className="detail-grid">
        <MemoryRail />
      </div>
    </div>
  );
}
