import React from 'react';
import { render, screen } from '@testing-library/react';

beforeAll(() => {
  Element.prototype.scrollTo = jest.fn();
});

jest.mock('./services/socketService', () => ({
  __esModule: true,
  default: {
    connect: () => ({
      on: jest.fn(),
      connect: jest.fn(),
    }),
    disconnect: jest.fn(),
    onFrame: jest.fn(),
    onAnalysisResult: jest.fn(),
    onError: jest.fn(),
    onSessionStarted: jest.fn(),
    onVODLoaded: jest.fn(),
    onVODReplayComplete: jest.fn(),
    startAnalysis: jest.fn(),
    stopAnalysis: jest.fn(),
    selectRegion: jest.fn(),
    loadVOD: jest.fn(),
    startVODReplay: jest.fn(),
  },
}));

jest.mock('./components/EmbodimentViewer', () => ({
  __esModule: true,
  default: ({ embodiment }: { embodiment: { display_name?: string } | null }) => (
    <div data-testid="embodiment-viewer">
      {embodiment ? embodiment.display_name : 'No 3D embodiment yet'}
    </div>
  ),
}));

import App from './App';

test('renders Joshinator shell with procedural embodiment panel', () => {
  render(<App />);
  expect(screen.getByText('Joshinator')).toBeInTheDocument();
  expect(screen.getByText('3D Embodiment')).toBeInTheDocument();
  expect(screen.getByTestId('embodiment-viewer')).toHaveTextContent('Mike Trout');
});
