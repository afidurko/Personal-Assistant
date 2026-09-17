import { describe, expect, it } from 'vitest';
import { camReply } from './cam-converse.js';

describe('camReply', () => {
  it('greets Aaron warmly', () => {
    expect(camReply('hi cam')).toMatch(/Aaron/i);
  });

  it('mentions listening when asked about mic', () => {
    expect(camReply('can you hear me')).toMatch(/listening/i);
  });

  it('acknowledges brain/cortex prompts', () => {
    expect(camReply('show me the 3d brain')).toMatch(/cortex|brain|fiber/i);
  });
});
