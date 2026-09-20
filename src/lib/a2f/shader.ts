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
  float lower = smoothstep(mouthCenter.y + 0.08, mouthCenter.y - 0.18, uv.y);
  p.y -= jawOpen * 0.045 * lower;
  p.z += jawOpen * 0.01 * lower;
  p.x += headYaw * 0.04;
  p.y += headPitch * 0.03;
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

  // Eye close — squash lids toward the iris
  vec2 dL = (uv - eyeL) / eyeSize;
  float inL = smoothstep(1.15, 0.35, length(dL));
  uv.y -= (uv.y - eyeL.y) * blinkL * inL * 0.85;

  vec2 dR = (uv - eyeR) / eyeSize;
  float inR = smoothstep(1.15, 0.35, length(dR));
  uv.y -= (uv.y - eyeR.y) * blinkR * inR * 0.85;

  // Mouth ellipse in UV
  vec2 msz = mouthSize * vec2(1.0 + smile * 0.18 - pucker * 0.12, 1.0);
  vec2 dm = (uv - mouthCenter) / msz;
  float er = length(vec2(dm.x, dm.y * 1.55));
  float inMouth = smoothstep(1.15, 0.42, er);

  // Peel lips apart (upper up, lower down) instead of stretching skin
  float split = jawOpen * 0.28 * inMouth;
  split += funnel * 0.06 * inMouth;
  if (uv.y >= mouthCenter.y) uv.y += split * 0.40;
  else uv.y -= split * 0.72;

  uv = clamp(uv, 0.001, 0.999);
  vec4 photo = texture2D(map, uv);

  vec3 cavity = vec3(0.18, 0.08, 0.07);
  vec3 teeth = vec3(0.93, 0.88, 0.82);
  float gap = inMouth * smoothstep(0.06, 0.2, jawOpen);
  float mid = (vUv.y - mouthCenter.y) + jawOpen * 0.008;
  float teethBand = gap * (1.0 - smoothstep(0.008, 0.034, abs(mid - 0.006)));
  vec3 hole = mix(cavity, teeth, teethBand);
  vec3 color = mix(photo.rgb, hole, gap * 0.94);

  gl_FragColor = vec4(color, 1.0);
}
`;
