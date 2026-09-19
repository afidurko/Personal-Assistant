/**
 * Loads a JSON catalog that maps detected target IDs → creature metadata.
 * This is the "what is it / what does it do" stage after recognition.
 */
AFRAME.registerComponent('card-catalog', {
  schema: {
    src: {type: 'string', default: 'catalog.json'}
  },

  init: function () {
    this.byId = {};
    this.ready = false;
    this._load();
  },

  _load: function () {
    var self = this;
    fetch(this.data.src)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        self.catalog = data;
        (data.cards || []).forEach(function (card) {
          self.byId[card.id] = card;
        });
        self.ready = true;
        self.el.emit('catalog-ready', {catalog: data});
      })
      .catch(function (err) {
        console.error('[card-catalog] failed to load', err);
        self.el.emit('catalog-error', {error: err});
      });
  },

  resolve: function (targetId) {
    return this.byId[targetId] || null;
  }
});
