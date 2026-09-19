/**
 * Orchestrates: detect → catalog resolve → spawn → interact.
 * Mirrors the Instagram AR card flow without Pokémon IP.
 */
AFRAME.registerComponent('recognition-pipeline', {
  init: function () {
    this.catalog = null;
    this._onReady = this._onReady.bind(this);
    this._onDetected = this._onDetected.bind(this);
    this._onMove = this._onMove.bind(this);
    this.el.sceneEl.addEventListener('catalog-ready', this._onReady);
    this.el.sceneEl.addEventListener('card-detected', this._onDetected);
    this.el.sceneEl.addEventListener('move-selected', this._onMove);
    this._log('Pipeline idle. Waiting for detection.');
  },

  remove: function () {
    this.el.sceneEl.removeEventListener('catalog-ready', this._onReady);
    this.el.sceneEl.removeEventListener('card-detected', this._onDetected);
    this.el.sceneEl.removeEventListener('move-selected', this._onMove);
  },

  _onReady: function (evt) {
    this.catalogComp = this.el.sceneEl.components['card-catalog'] ||
      (this.el.sceneEl.querySelector('[card-catalog]') &&
        this.el.sceneEl.querySelector('[card-catalog]').components['card-catalog']);
    this._log('Catalog loaded (' + (evt.detail.catalog.cards || []).length + ' cards).');
  },

  _onDetected: function (evt) {
    var cardId = evt.detail.cardId;
    var anchorEl = evt.detail.anchorEl;
    if (!this.catalogComp || !this.catalogComp.ready) {
      this._log('Catalog not ready yet.');
      return;
    }
    var card = this.catalogComp.resolve(cardId);
    if (!card) {
      this._log('Unknown target: ' + cardId);
      return;
    }
    // Clone so runtime HP mutations don't corrupt the catalog.
    var resolved = JSON.parse(JSON.stringify(card));
    this._log('Resolved ' + resolved.name + ' — spawning 3D character.');
    this.el.sceneEl.emit('card-resolved', {
      card: resolved,
      anchorEl: anchorEl
    });
  },

  _onMove: function (evt) {
    var move = evt.detail.move;
    var cardId = evt.detail.cardId;
    var banner = document.getElementById('action-banner');
    var text = (cardId + ' used ' + move.label + '!').toUpperCase();
    if (banner) { banner.textContent = text; }
    this._log(text);

    var creature = evt.detail.creatureEl;
    if (creature) {
      creature.setAttribute('animation__punch', {
        property: 'position',
        from: '0 0.05 0.35',
        to: '0 0.12 0.55',
        dur: 180,
        dir: 'alternate',
        loop: 1,
        easing: 'easeOutQuad'
      });
    }

    // Demo: damaging moves hit the other active spawn if present.
    if (move.damage > 0) {
      var spawnerComp = this.el.sceneEl.components['character-spawner'];
      if (spawnerComp && spawnerComp.active) {
        Object.keys(spawnerComp.active).forEach(function (id) {
          if (id !== cardId) {
            spawnerComp.applyDamage(id, move.damage);
          }
        });
      }
    }
  },

  _log: function (msg) {
    var el = document.getElementById('pipeline-log');
    if (el) {
      var line = document.createElement('div');
      line.textContent = msg;
      el.prepend(line);
      while (el.childElementCount > 6) {
        el.removeChild(el.lastChild);
      }
    }
  }
});
