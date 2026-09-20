/** Photo-plane shader: Cam’s real portrait + NVIDIA A2F ARKit weights. */

export const CAM_A2F_VERT = /* glsl */ `
varying vec2 vUv;
uniform float jawOpen;
uniform float headYaw;
uniform float headPitch;
uniform vec2 mouthCenter;
void main() {
  vUv = uv;
  vec3 p = position;
  float lower = smoothstep(mouthCenter.y + 0.06, mouthCenter.y - 0.16, uv.y);
  p.y -= jawOpen * 0.02 * lower;
  p.x += headYaw * 0.03;
  p.y += headPitch * 0.02;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
}
`;

export const CAM_A2F_FRAG = /* glsl */ `
varying vec2 vUv;
uniform sampler2D map;
uniform float jawOpen;
uniform float smile;
uniform float blinkL;
uniform float blinkR;
uniform float funnel;
uniform float pucker;
uniform vec2 mouthCenter;
uniform vec2 mouthSize;
uniform vec2 eyeL;
uniform vec2 eyeR;
uniform vec2 eyeSize;

void main() {
  vec2 uv = vUv;

  vec2 dL = (uv - eyeL) / eyeSize;
  float inL = smoothstep(1.05, 0.32, length(dL));
  uv.y -= (uv.y - eyeL.y) * blinkL * inL * 0.75;

  vec2 dR = (uv - eyeR) / eyeSize;
  float inR = smoothstep(1.05, 0.32, length(dR));
  uv.y -= (uv.y - eyeR.y) * blinkR * inR * 0.75;

  float open = clamp(jawOpen, 0.0, 0.5);
  // Inner aperture — lip-shaped oval, not a wide bar
  vec2 msz = vec2(
    mouthSize.x * (0.48 + smile * 0.06 - pucker * 0.08),
    mix(0.009, 0.034, open) + funnel * 0.006
  );
  vec2 dm = (vUv - mouthCenter) / max(msz, vec2(0.001));
  float er = length(dm);
  float lips = smoothstep(1.25, 0.7, er);
  float inner = smoothstep(0.92, 0.28, er);

  float split = (open * 0.09 + funnel * 0.02) * lips;
  if (uv.y >= mouthCenter.y) uv.y += split * 0.35;
  else uv.y -= split * 0.5;

  uv = clamp(uv, 0.001, 0.999);
  vec4 photo = texture2D(map, uv);

  float gap = inner * smoothstep(0.05, 0.22, open);
  vec3 cavity = vec3(0.17, 0.07, 0.07);
  vec3 color = mix(photo.rgb, cavity, gap * 0.78);

  gl_FragColor = vec4(color, 1.0);
}
`;
