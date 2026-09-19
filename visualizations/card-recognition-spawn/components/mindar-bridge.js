/**
 * Bridges MindAR `targetFound` / `targetLost` into the shared pipeline event bus.
 *
 * schema.targetMap: "0:volt-wisp,1:ember-drake,2:tide-finch"
 */
AFRAME.registerComponent('mindar-bridge', {
  schema: {
    targetMap: {type: 'string', default: ''}
  },

  init: function () {
    this.map = {};
    this.data.targetMap.split(',').forEach(function (pair) {
      var parts = pair.trim().split(':');
      if (parts.length === 2) {
        this.map[parts[0].trim()] = parts[1].trim();
      }
    }.bind(this));

    this._onFound = this._onFound.bind(this);
    this._onLost = this._onLost.bind(this);

    var targets = this.el.querySelectorAll('[mindar-image-target]');
    for (var i = 0; i < targets.length; i++) {
      targets[i].addEventListener('targetFound', this._onFound);
      targets[i].addEventListener('targetLost', this._onLost);
    }

    // Optional: start MindAR only after catalog is ready.
    this.el.sceneEl.addEventListener('catalog-ready', function () {
      var sys = this.el.sceneEl.systems['mindar-image-system'];
      if (sys && sys.start) {
        sys.start();
      }
    }.bind(this));
  },

  _onFound: function (evt) {
    var el = evt.target;
    var index = el.getAttribute('mindar-image-target').targetIndex;
    var cardId = el.getAttribute('data-card-id') || this.map[String(index)];
    if (!cardId) { return; }
    var detector = this.el.sceneEl.components['card-detector'];
    if (detector) {
      detector.reportDetection(cardId, el);
    } else {
      this.el.sceneEl.emit('card-detected', {cardId: cardId, anchorEl: el});
    }
  },

  _onLost: function (evt) {
    // Keep last spawn; production apps may hide or fade the character here.
    this.el.sceneEl.emit('card-lost', {anchorEl: evt.target});
  }
});
