/**
 * HTML fallback when WebGL cannot show the A-Frame canvas (e.g. software GL).
 * Uses the same catalog + event bus so detection → identity → “more than 2D” still demos.
 */
(function () {
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === 'className') node.className = attrs[k];
        else if (k === 'text') node.textContent = attrs[k];
        else node.setAttribute(k, attrs[k]);
      });
    }
    (children || []).forEach(function (c) {
      if (typeof c === 'string') node.appendChild(document.createTextNode(c));
      else if (c) node.appendChild(c);
    });
    return node;
  }

  function needsFallback() {
    try {
      var c = document.createElement('canvas');
      var gl = c.getContext('webgl') || c.getContext('experimental-webgl');
      if (!gl) return true;
      var dbg = gl.getExtension('WEBGL_debug_renderer_info');
      if (dbg) {
        var renderer = String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || '');
        if (/swiftshader|llvmpipe|software/i.test(renderer)) return true;
      }
    } catch (e) {
      return true;
    }
    return /fallback=1|html=1/.test(location.search);
  }

  function mount() {
    if (!needsFallback() && !/force-html=1/.test(location.search)) {
      // Still expose a small HTML scan strip for accessibility.
    }

    var root = el('div', {id: 'html-lab', className: 'html-lab'});
    root.innerHTML = '';
    var title = el('div', {className: 'html-lab-title', text: 'HTML lab desk (WebGL fallback)'});
    var cardsRow = el('div', {className: 'html-cards'});
    var stage = el('div', {className: 'html-stage'});
    stage.appendChild(el('div', {className: 'html-arena'}));
    var spawnHost = el('div', {id: 'html-spawns', className: 'html-spawns'});
    stage.appendChild(spawnHost);
    root.appendChild(title);
    root.appendChild(cardsRow);
    root.appendChild(stage);
    document.body.appendChild(root);

    var catalog = [];
    fetch('catalog.json')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        catalog = data.cards || [];
        catalog.forEach(function (card) {
          var btn = el('button', {
            className: 'html-card',
            type: 'button',
            'data-card-id': card.id
          });
          btn.style.background = 'linear-gradient(145deg, ' + card.color + ', #111)';
          btn.appendChild(el('strong', {text: card.name}));
          btn.appendChild(el('span', {text: card.type + ' · HP ' + card.hp}));
          btn.addEventListener('click', function () {
            var scene = document.querySelector('a-scene');
            var detector = scene && scene.components && scene.components['card-detector'];
            if (detector) {
              detector.reportDetection(card.id, null);
            } else if (scene) {
              scene.emit('card-detected', {cardId: card.id, anchorEl: null});
            }
          });
          cardsRow.appendChild(btn);
        });
      });

    var active = {};

    function renderSpawn(card) {
      if (active[card.id]) active[card.id].remove();
      var panel = el('div', {className: 'html-spawn', 'data-card-id': card.id});
      panel.style.setProperty('--c', card.color);
      var creature = el('div', {className: 'html-creature shape-' + card.shape});
      var meta = el('div', {className: 'html-meta'});
      meta.appendChild(el('div', {className: 'html-name', text: card.name}));
      var hp = el('div', {className: 'html-hp', text: 'HP ' + card.hp + ' / ' + card.maxHp});
      meta.appendChild(hp);
      var moves = el('div', {className: 'html-moves'});
      (card.moves || []).forEach(function (move) {
        var m = el('button', {type: 'button', className: 'html-move', text: move.label});
        m.addEventListener('click', function () {
          var scene = document.querySelector('a-scene');
          if (scene) {
            scene.emit('move-selected', {
              cardId: card.id,
              move: move,
              creatureEl: null
            });
          }
          var banner = document.getElementById('action-banner');
          if (banner) {
            banner.textContent = (card.id + ' used ' + move.label + '!').toUpperCase();
          }
          // Apply damage in HTML view to other spawns
          if (move.damage > 0) {
            Object.keys(active).forEach(function (id) {
              if (id === card.id) return;
              var other = active[id];
              var state = other._state;
              state.hp = Math.max(0, state.hp - move.damage);
              other._hpEl.textContent = 'HP ' + state.hp + ' / ' + state.maxHp;
            });
          }
          creature.classList.remove('punch');
          void creature.offsetWidth;
          creature.classList.add('punch');
        });
        moves.appendChild(m);
      });
      meta.appendChild(moves);
      panel.appendChild(creature);
      panel.appendChild(meta);
      panel._state = {hp: card.hp, maxHp: card.maxHp};
      panel._hpEl = hp;
      spawnHost.appendChild(panel);
      active[card.id] = panel;
    }

    // Prefer scene events when A-Frame is alive; also listen for character-spawned.
    function bindScene() {
      var scene = document.querySelector('a-scene');
      if (!scene) {
        setTimeout(bindScene, 200);
        return;
      }
      scene.addEventListener('card-resolved', function (evt) {
        renderSpawn(evt.detail.card);
      });
      scene.addEventListener('character-spawned', function (evt) {
        // Ensure HTML mirror exists even if 3D spawn succeeded invisibly.
        if (!active[evt.detail.card.id]) renderSpawn(evt.detail.card);
      });
    }
    bindScene();

    var status = document.getElementById('detect-status');
    if (status && needsFallback()) {
      status.textContent = 'WebGL software fallback — use HTML lab desk below to scan cards.';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
