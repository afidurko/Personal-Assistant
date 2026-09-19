/**
 * Builds a lightweight 3D creature from primitives so a recognized 2D card
 * becomes more than a floating texture — without requiring external glTF IP.
 */
AFRAME.registerComponent('procedural-creature', {
  schema: {
    shape: {type: 'string', default: 'wisp'},
    color: {type: 'color', default: '#F5C542'},
    accent: {type: 'color', default: '#2B1B0E'},
    scale: {type: 'number', default: 0.35}
  },

  init: function () {
    this._build();
  },

  update: function () {
    this._clear();
    this._build();
  },

  _clear: function () {
    while (this.el.firstChild) {
      this.el.removeChild(this.el.firstChild);
    }
  },

  _build: function () {
    var root = this.el;
    root.setAttribute('scale', {
      x: this.data.scale,
      y: this.data.scale,
      z: this.data.scale
    });

    var body = document.createElement('a-entity');
    var eyeL = document.createElement('a-sphere');
    var eyeR = document.createElement('a-sphere');
    eyeL.setAttribute('radius', 0.08);
    eyeR.setAttribute('radius', 0.08);
    eyeL.setAttribute('color', '#111');
    eyeR.setAttribute('color', '#111');

    if (this.data.shape === 'drake') {
      body.setAttribute('geometry', {primitive: 'cone', radiusBottom: 0.45, radiusTop: 0.12, height: 1.1});
      body.setAttribute('material', {color: this.data.color, roughness: 0.45, metalness: 0.15});
      body.setAttribute('position', '0 0.55 0');
      eyeL.setAttribute('position', '-0.16 0.95 0.28');
      eyeR.setAttribute('position', '0.16 0.95 0.28');
      this._limb(root, '-0.42 0.35 0.05', this.data.accent, '0 0 -35');
      this._limb(root, '0.42 0.35 0.05', this.data.accent, '0 0 35');
      this._flame(root);
    } else if (this.data.shape === 'finch') {
      body.setAttribute('geometry', {primitive: 'sphere', radius: 0.42});
      body.setAttribute('material', {color: this.data.color, roughness: 0.35});
      body.setAttribute('position', '0 0.55 0');
      eyeL.setAttribute('position', '-0.14 0.62 0.34');
      eyeR.setAttribute('position', '0.14 0.62 0.34');
      this._wing(root, '-0.55 0.55 0', this.data.accent, '0 0 25');
      this._wing(root, '0.55 0.55 0', this.data.accent, '0 0 -25');
      var beak = document.createElement('a-cone');
      beak.setAttribute('radius-bottom', 0.08);
      beak.setAttribute('radius-top', 0.01);
      beak.setAttribute('height', 0.28);
      beak.setAttribute('color', '#F2D27A');
      beak.setAttribute('rotation', '90 0 0');
      beak.setAttribute('position', '0 0.52 0.45');
      root.appendChild(beak);
    } else {
      // wisp
      body.setAttribute('geometry', {primitive: 'sphere', radius: 0.4});
      body.setAttribute('material', {
        color: this.data.color,
        emissive: this.data.color,
        emissiveIntensity: 0.35,
        roughness: 0.2,
        metalness: 0.4
      });
      body.setAttribute('position', '0 0.55 0');
      eyeL.setAttribute('position', '-0.14 0.62 0.32');
      eyeR.setAttribute('position', '0.14 0.62 0.32');
      this._orb(root, '0 0.15 0', this.data.accent);
    }

    root.appendChild(body);
    root.appendChild(eyeL);
    root.appendChild(eyeR);

    root.setAttribute('animation__bob', {
      property: 'position',
      dir: 'alternate',
      dur: 1400,
      easing: 'easeInOutSine',
      loop: true,
      to: '0 0.08 0'
    });
  },

  _limb: function (root, pos, color, rot) {
    var limb = document.createElement('a-cylinder');
    limb.setAttribute('radius', 0.07);
    limb.setAttribute('height', 0.55);
    limb.setAttribute('color', color);
    limb.setAttribute('position', pos);
    limb.setAttribute('rotation', rot);
    root.appendChild(limb);
  },

  _wing: function (root, pos, color, rot) {
    var wing = document.createElement('a-plane');
    wing.setAttribute('width', 0.55);
    wing.setAttribute('height', 0.28);
    wing.setAttribute('color', color);
    wing.setAttribute('opacity', 0.85);
    wing.setAttribute('position', pos);
    wing.setAttribute('rotation', rot);
    wing.setAttribute('side', 'double');
    wing.setAttribute('animation__flap', {
      property: 'rotation',
      dir: 'alternate',
      dur: 500,
      loop: true,
      to: rot.split(' ').map(function (v, i) { return i === 2 ? (parseFloat(v) + 20) : v; }).join(' ')
    });
    root.appendChild(wing);
  },

  _flame: function (root) {
    var flame = document.createElement('a-cone');
    flame.setAttribute('radius-bottom', 0.12);
    flame.setAttribute('radius-top', 0.01);
    flame.setAttribute('height', 0.35);
    flame.setAttribute('color', '#FFB347');
    flame.setAttribute('position', '0 1.2 0');
    flame.setAttribute('animation__flicker', {
      property: 'scale',
      dir: 'alternate',
      dur: 280,
      loop: true,
      to: '1.15 1.3 1.15'
    });
    root.appendChild(flame);
  },

  _orb: function (root, pos, color) {
    var orb = document.createElement('a-torus');
    orb.setAttribute('radius', 0.35);
    orb.setAttribute('radius-tubular', 0.03);
    orb.setAttribute('color', color);
    orb.setAttribute('position', pos);
    orb.setAttribute('rotation', '90 0 0');
    orb.setAttribute('animation__spin', {
      property: 'rotation',
      dur: 4000,
      loop: true,
      easing: 'linear',
      to: '90 360 0'
    });
    root.appendChild(orb);
  }
});
