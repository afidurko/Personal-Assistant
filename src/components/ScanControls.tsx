interface ScanControlsProps {
  scanning: boolean;
  cycleCount: number;
  lastCycleAt: string | null;
  connected: boolean;
  onStart: () => void;
  onStop: () => void;
}

function formatCycle(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return '—';
  }
}

export function ScanControls({
  scanning,
  cycleCount,
  lastCycleAt,
  connected,
  onStart,
  onStop,
}: ScanControlsProps) {
  return (
    <div className="scan-controls">
      {scanning ? (
        <button type="button" className="btn btn-active" onClick={onStop} disabled={!connected}>
          Stop continuous scan
        </button>
      ) : (
        <button type="button" className="btn" onClick={onStart} disabled={!connected}>
          Start continuous scan
        </button>
      )}
      <span className="scan-stat">
        Cycles <strong>{cycleCount}</strong>
      </span>
      <span className="scan-stat">
        Last <strong>{formatCycle(lastCycleAt)}</strong>
      </span>
    </div>
  );
}
