/**
 * Spawns the "more than 2D" visualization for a resolved card:
 * floating digital card, 3D creature, HP bar, and move buttons.
 */
AFRAME.registerComponent('character-spawner', {
  schema: {
    spawnRoot: {type: 'selector', default: '#spawn-root'}
  },

  init: function () {
    this.active = {};
    this._onResolved = this._onResolved.bind(this);
    this.el.sceneEl.addEventListener('card-resolved', this._onResolved);
  },

  remove: function () {
    this.el.sceneEl.removeEventListener('card-resolved', this._onResolved);
  },

  _onResolved: function (evt) {
    var card = evt.detail.card;
    var anchorEl = evt.detail.anchorEl;
    if (!card) { return; }
    this.spawn(card, anchorEl);
  },

  spawn: function (card, anchorEl) {
    var root = this.data.spawnRoot || this.el;
    if (this.active[card.id]) {
      this.active[card.id].parentNode.removeChild(this.active[card.id]);
      delete this.active[card.id];
    }

    var group = document.createElement('a-entity');
    group.setAttribute('id', 'spawn-' + card.id);
    group.classList.add('spawned-character');

    if (anchorEl && anchorEl.object3D) {
      var pos = new AFRAME.THREE.Vector3();
      var quat = new AFRAME.THREE.Quaternion();
      anchorEl.object3D.getWorldPosition(pos);
      anchorEl.object3D.getWorldQuaternion(quat);
      // Lift off the table card into the play space above it.
      pos.y += 0.02;
      group.object3D.position.copy(pos);
      // Keep upright on the table plane for lab mode.
      group.object3D.rotation.set(0, anchorEl.object3D.rotation.y, 0);
    } else {
      group.setAttribute('position', '0 0.02 -1.2');
    }

    // Semi-transparent digital card floating above the physical card.
    var digitalCard = document.createElement('a-plane');
    digitalCard.setAttribute('width', 0.42);
    digitalCard.setAttribute('height', 0.58);
    digitalCard.setAttribute('position', '0 0.45 0');
    digitalCard.setAttribute('material', {
      color: card.color,
      opacity: 0.55,
      transparent: true,
      side: 'double'
    });
    digitalCard.setAttribute('animation__float', {
      property: 'position',
      dir: 'alternate',
      dur: 1800,
      loop: true,
      to: '0 0.52 0',
      easing: 'easeInOutSine'
    });
    group.appendChild(digitalCard);

    var title = document.createElement('a-text');
    title.setAttribute('value', card.name.toUpperCase());
    title.setAttribute('align', 'center');
    title.setAttribute('width', 0.9);
    title.setAttribute('color', '#fff');
    title.setAttribute('position', '0 0.72 0.02');
    group.appendChild(title);

    // 3D creature — the key step beyond a 2D overlay.
    var creature = document.createElement('a-entity');
    creature.setAttribute('position', '0 0.05 0.35');
    creature.setAttribute('procedural-creature', {
      shape: card.shape,
      color: card.color,
      accent: card.accent,
      scale: card.modelScale || 0.35
    });
    group.appendChild(creature);

    // HP bar
    var hpRoot = document.createElement('a-entity');
    hpRoot.setAttribute('position', '0 1.05 0.35');
    var hpBg = document.createElement('a-plane');
    hpBg.setAttribute('width', 0.5);
    hpBg.setAttribute('height', 0.06);
    hpBg.setAttribute('color', '#222');
    hpBg.setAttribute('opacity', 0.7);
    var hpFill = document.createElement('a-plane');
    hpFill.setAttribute('class', 'hp-fill');
    hpFill.setAttribute('width', 0.48);
    hpFill.setAttribute('height', 0.045);
    hpFill.setAttribute('color', '#5DDB7A');
    hpFill.setAttribute('position', '0 0 0.001');
    var hpText = document.createElement('a-text');
    hpText.setAttribute('class', 'hp-text');
    hpText.setAttribute('value', 'HP ' + card.hp + ' / ' + card.maxHp);
    hpText.setAttribute('align', 'center');
    hpText.setAttribute('width', 1.1);
    hpText.setAttribute('color', '#fff');
    hpText.setAttribute('position', '0 0.08 0.01');
    hpRoot.appendChild(hpBg);
    hpRoot.appendChild(hpFill);
    hpRoot.appendChild(hpText);
    group.appendChild(hpRoot);

    // Move buttons (spatial UI)
    var moves = document.createElement('a-entity');
    moves.setAttribute('position', '0.55 0.55 0.2');
    moves.setAttribute('class', 'move-panel');
    (card.moves || []).forEach(function (move, i) {
      var btn = document.createElement('a-plane');
      btn.setAttribute('class', 'move-btn');
      btn.setAttribute('width', 0.55);
      btn.setAttribute('height', 0.14);
      btn.setAttribute('color', '#2A3340');
      btn.setAttribute('opacity', 0.92);
      btn.setAttribute('position', '0 ' + (0.2 - i * 0.17) + ' 0');
      btn.setAttribute('data-move-id', move.id);
      btn.setAttribute('data-card-id', card.id);
      btn.setAttribute('data-damage', move.damage);
      var label = document.createElement('a-text');
      label.setAttribute('value', move.label);
      label.setAttribute('align', 'center');
      label.setAttribute('width', 1.2);
      label.setAttribute('color', '#F4F7FB');
      label.setAttribute('position', '0 0 0.01');
      btn.appendChild(label);
      btn.addEventListener('click', function () {
        btn.sceneEl.emit('move-selected', {
          cardId: card.id,
          move: move,
          creatureEl: creature
        });
      });
      moves.appendChild(btn);
    });
    group.appendChild(moves);

    group.cardState = {
      hp: card.hp,
      maxHp: card.maxHp,
      hpFill: hpFill,
      hpText: hpText,
      creature: creature
    };

    root.appendChild(group);
    // Ensure object3D pose applied if we set it manually before attach.
    if (anchorEl && anchorEl.object3D && group.object3D) {
      var p = new AFRAME.THREE.Vector3();
      anchorEl.object3D.getWorldPosition(p);
      p.y += 0.02;
      group.object3D.position.copy(p);
    }

    this.active[card.id] = group;
    this.el.sceneEl.emit('character-spawned', {card: card, entity: group});
    return group;
  },

  applyDamage: function (cardId, amount) {
    var group = this.active[cardId];
    if (!group || !group.cardState) { return; }
    var state = group.cardState;
    state.hp = Math.max(0, state.hp - amount);
    var ratio = state.maxHp ? state.hp / state.maxHp : 0;
    state.hpFill.setAttribute('width', 0.48 * ratio);
    state.hpFill.setAttribute('position', ((0.48 * ratio) - 0.48) / 2 + ' 0 0.001');
    state.hpText.setAttribute('value', 'HP ' + state.hp + ' / ' + state.maxHp);
    if (state.hp <= 0) {
      state.hpFill.setAttribute('color', '#E85D3A');
    }
  }
});
