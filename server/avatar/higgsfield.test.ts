import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { underRoot } from './higgsfield.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

describe('higgsfield underRoot', () => {
  it('accepts the identity portrait', () => {
    expect(underRoot('identity/persona/cam-face.jpg')).toBe(
      path.join(ROOT, 'identity/persona/cam-face.jpg'),
    );
  });

  it('rejects path escape', () => {
    expect(underRoot('../etc/passwd')).toBeNull();
  });
});
