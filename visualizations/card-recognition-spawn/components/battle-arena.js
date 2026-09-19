/**
 * Table-scale battle arena — the shared stage characters stand on after scan.
 */
AFRAME.registerComponent('battle-arena', {
  schema: {
    radius: {type: 'number', default: 0.85},
    color: {type: 'color', default: '#1FAE5A'}
  },

  init: function () {
    this._build();
    this._onSpawn = this._onSpawn.bind(this);
    this.el.sceneEl.addEventListener('character-spawned', this._onSpawn);
  },

  remove: function () {
    this.el.sceneEl.removeEventListener('character-spawned', this._onSpawn);
  },

  _build: function () {
    var disc = document.createElement('a-ring');
    disc.setAttribute('radius-inner', this.data.radius * 0.15);
    disc.setAttribute('radius-outer', this.data.radius);
    disc.setAttribute('color', this.data.color);
    disc.setAttribute('opacity', 0.55);
    disc.setAttribute('rotation', '-90 0 0');
    disc.setAttribute('material', {transparent: true, side: 'double'});
    this.el.appendChild(disc);

    var rim = document.createElement('a-torus');
    rim.setAttribute('radius', this.data.radius);
    rim.setAttribute('radius-tubular', 0.012);
    rim.setAttribute('color', '#7CFFF0');
    rim.setAttribute('opacity', 0.85);
    rim.setAttribute('rotation', '-90 0 0');
    rim.setAttribute('animation__pulse', {
      property: 'scale',
      dir: 'alternate',
      dur: 1600,
      loop: true,
      to: '1.03 1.03 1.03'
    });
    this.el.appendChild(rim);

    var crossA = document.createElement('a-plane');
    crossA.setAttribute('width', this.data.radius * 1.6);
    crossA.setAttribute('height', 0.02);
    crossA.setAttribute('color', '#E8FFF4');
    crossA.setAttribute('opacity', 0.45);
    crossA.setAttribute('rotation', '-90 0 0');
    crossA.setAttribute('position', '0 0.002 0');
    this.el.appendChild(crossA);

    var crossB = document.createElement('a-plane');
    crossB.setAttribute('width', 0.02);
    crossB.setAttribute('height', this.data.radius * 1.6);
    crossB.setAttribute('color', '#E8FFF4');
    crossB.setAttribute('opacity', 0.45);
    crossB.setAttribute('rotation', '-90 0 0');
    crossB.setAttribute('position', '0 0.002 0');
    this.el.appendChild(crossB);
  },

  _onSpawn: function () {
    this.el.setAttribute('visible', true);
    this.el.setAttribute('animation__appear', {
      property: 'scale',
      from: '0.2 0.2 0.2',
      to: '1 1 1',
      dur: 450,
      easing: 'easeOutElastic'
    });
  }
});
