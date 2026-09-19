/**
 * Detection stage.
 *
 * Lab mode: clicking a physical-looking card proxy emits `card-detected`
 * (so the pipeline can be tested without a camera / printed targets).
 *
 * MindAR / external CV can call the same public API:
 *   el.components['card-detector'].reportDetection(id, poseEntity)
 */
AFRAME.registerComponent('card-detector', {
  schema: {
    mode: {type: 'string', default: 'lab'}, // lab | external
    activeClass: {type: 'string', default: 'detectable-card'}
  },

  init: function () {
    this._boundCards = [];
    this._bindCards = this._bindCards.bind(this);
    if (this.el.sceneEl.hasLoaded) {
      this._bindCards();
    } else {
      this.el.sceneEl.addEventListener('loaded', this._bindCards);
    }
    this._setStatus('Lab mode: tap a card on the table to scan.');
  },

  remove: function () {
    this.el.sceneEl.removeEventListener('loaded', this._bindCards);
    this._boundCards.forEach(function (el) {
      el.removeEventListener('click', el.__cardDetectHandler);
    });
    this._boundCards = [];
  },

  _bindCards: function () {
    if (this.data.mode !== 'lab') { return; }
    var cards = this.el.sceneEl.querySelectorAll('.' + this.data.activeClass);
    var self = this;
    for (var i = 0; i < cards.length; i++) {
      (function (cardEl) {
        cardEl.__cardDetectHandler = function () {
          var id = cardEl.getAttribute('data-card-id');
          if (id) { self.reportDetection(id, cardEl); }
        };
        cardEl.addEventListener('click', cardEl.__cardDetectHandler);
        self._boundCards.push(cardEl);
      })(cards[i]);
    }
  },

  /**
   * Shared entry for any detector (lab click, MindAR target found, PaddleDetection).
   * @param {string} cardId catalog id
   * @param {Element} [anchorEl] entity whose world pose anchors the spawn
   */
  reportDetection: function (cardId, anchorEl) {
    this._setStatus('Detected: ' + cardId);
    this.el.sceneEl.emit('card-detected', {
      cardId: cardId,
      anchorEl: anchorEl || null,
      at: performance.now()
    });
  },

  _setStatus: function (text) {
    var status = document.getElementById('detect-status');
    if (status) { status.textContent = text; }
  }
});
