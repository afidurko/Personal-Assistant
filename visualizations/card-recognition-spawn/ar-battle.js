/**
 * AR phone-composite battle flow matching the reference screenshots:
 * setup brackets → + scan → arena + 3D fighters + holo card + moves → action banner
 */
(function () {
  var catalog = {
    'volt-wisp': {
      id: 'volt-wisp',
      name: 'Volt Wisp',
      hp: 90,
      maxHp: 90,
      moves: [
        { id: 'spark-jab', label: 'Spark Jab', damage: 20 },
        { id: 'arc-combo', label: 'Arc Combo', damage: 40 },
        { id: 'retreat', label: 'Retreat', damage: 0 }
      ]
    },
    'ember-drake': {
      id: 'ember-drake',
      name: 'Ember Drake',
      hp: 80,
      maxHp: 80,
      moves: [
        { id: 'cinder-tap', label: 'Cinder Tap', damage: 20 },
        { id: 'flare-rush', label: 'Flare Rush', damage: 35 },
        { id: 'retreat', label: 'Retreat', damage: 0 }
      ]
    }
  };

  var state = {
    step: 1,
    you: null,
    opp: null,
    turn: 'you'
  };

  var view = document.getElementById('ar-view');
  var scanBtn = document.getElementById('scan-btn');
  var banner = document.getElementById('action-banner');
  var setupStep = document.getElementById('setup-step');
  var setupCopy = document.getElementById('setup-copy');
  var logTitle = document.getElementById('log-title');
  var logBody = document.getElementById('log-body');
  var movesEl = document.getElementById('moves');

  function setBanner(text) {
    banner.textContent = text;
    banner.classList.remove('show');
    void banner.offsetWidth;
    if (text) banner.classList.add('show');
  }

  function setHp( whofight, card) {
    var fill = document.getElementById(whofight === 'you' ? 'hp-you-fill' : 'hp-opp-fill');
    var text = document.getElementById(whofight === 'you' ? 'hp-you-text' : 'hp-opp-text');
    var ratio = card.maxHp ? card.hp / card.maxHp : 0;
    fill.style.width = Math.max(0, ratio * 100) + '%';
    fill.style.background = ratio < 0.3
      ? 'linear-gradient(90deg, #d9483b, #ff8a70)'
      : 'linear-gradient(90deg, #3dca63, #7dff9a)';
    text.textContent = 'HP ' + card.hp + ' / ' + card.maxHp;
  }

  function enterBattle() {
    view.classList.remove('mode-setup');
    view.classList.add('mode-battle', 'has-arena');

    document.getElementById('holo-active').hidden = false;
    document.getElementById('active-hp').hidden = false;
    document.getElementById('card-opp').hidden = false;
    document.getElementById('holo-opp').hidden = false;

    document.getElementById('fighter-you').hidden = false;
    document.getElementById('fighter-opp').hidden = false;
    setHp('you', state.you);
    setHp('opp', state.opp);

    movesEl.hidden = false;
    document.getElementById('panel-wait').hidden = false;

    logTitle.textContent = 'YOUR TURN';
    logBody.textContent = '1. Scanned Volt Wisp into Active.';
    setBanner('');
    setupCopy.textContent = '';
  }

  function scan() {
    if (state.step === 1) {
      // Recognize the physical card in ACTIVE brackets
      state.you = JSON.parse(JSON.stringify(catalog['volt-wisp']));
      state.step = 2;
      setupStep.textContent = '2 / 3';
      setupCopy.textContent = 'Card recognized: Volt Wisp. Spawning 3D form…';
      logTitle.textContent = 'DETECTED';
      logBody.textContent = 'Volt Wisp · Energy · HP 90';
      view.classList.add('has-arena');
      document.getElementById('holo-active').hidden = false;
      document.getElementById('active-hp').hidden = false;
      document.getElementById('fighter-you').hidden = false;
      setHp('you', state.you);
      setBanner('VOLT WISP ENTERED THE FIELD');

      window.setTimeout(function () {
        setupStep.textContent = '3 / 3';
        setupCopy.textContent = 'Opponent card found. Dwell on + to start battle.';
        document.getElementById('card-opp').hidden = false;
        document.getElementById('zone-opp').style.opacity = '1';
        state.step = 3;
      }, 900);
      return;
    }

    if (state.step === 3) {
      state.opp = JSON.parse(JSON.stringify(catalog['ember-drake']));
      document.getElementById('holo-opp').hidden = false;
      document.getElementById('fighter-opp').hidden = false;
      setHp('opp', state.opp);
      setBanner('EMBER DRAKE ENTERED THE FIELD');
      window.setTimeout(enterBattle, 700);
    }
  }

  function useMove(moveId) {
    if (!state.you || !state.opp || view.classList.contains('mode-setup')) return;
    var move = state.you.moves.find(function (m) { return m.id === moveId; });
    if (!move) return;

    if (move.id === 'retreat') {
      setBanner('VOLT WISP RETREATED');
      logTitle.textContent = 'YOUR TURN';
      logBody.textContent = '1. Retreated.';
      return;
    }

    var youFighter = document.getElementById('fighter-you');
    var oppFighter = document.getElementById('fighter-opp');
    youFighter.classList.remove('punch');
    void youFighter.offsetWidth;
    youFighter.classList.add('punch');

    state.opp.hp = Math.max(0, state.opp.hp - move.damage);
    window.setTimeout(function () {
      oppFighter.classList.remove('hit');
      void oppFighter.offsetWidth;
      oppFighter.classList.add('hit');
      setHp('opp', state.opp);
      document.getElementById('active-hp').innerHTML =
        'ACTIVE · <b>' + state.you.hp + ' / ' + state.you.maxHp + ' HP</b>';
    }, 180);

    setBanner('VOLT WISP USED ' + move.label.toUpperCase() + '!');
    logTitle.textContent = 'YOUR TURN';
    logBody.innerHTML = '1. Used ' + move.label + '.<br>2. Opponent HP ' + state.opp.hp + '/' + state.opp.maxHp;

    if (state.opp.hp <= 0) {
      window.setTimeout(function () {
        setBanner('EMBER DRAKE FAINTED');
        logTitle.textContent = 'YOU WIN';
        logBody.textContent = 'Opponent knocked out.';
        document.getElementById('panel-wait').textContent = 'Victory';
      }, 600);
      return;
    }

    // Opponent reply beat — mirrors “OPPONENT TURN” panel in the reference
    window.setTimeout(function () {
      document.getElementById('panel-wait').hidden = true;
      logTitle.textContent = 'OPPONENT TURN';
      logBody.textContent = '1. Drew 1 card.';
      var counter = state.opp.moves[0];
      state.you.hp = Math.max(0, state.you.hp - counter.damage);
      oppFighter.classList.remove('punch');
      void oppFighter.offsetWidth;
      oppFighter.classList.add('punch');
      setHp('you', state.you);
      document.getElementById('active-hp').innerHTML =
        'ACTIVE · <b>' + state.you.hp + ' / ' + state.you.maxHp + ' HP</b>';
      setBanner('EMBER DRAKE USED ' + counter.label.toUpperCase() + '!');
      window.setTimeout(function () {
        document.getElementById('panel-wait').hidden = false;
        document.getElementById('panel-wait').textContent = 'Waiting…';
        logTitle.textContent = 'YOUR TURN';
        logBody.textContent = 'Choose an attack.';
      }, 1100);
    }, 1200);
  }

  scanBtn.addEventListener('click', scan);
  movesEl.addEventListener('click', function (evt) {
    var btn = evt.target.closest('button[data-move]');
    if (!btn) return;
    useMove(btn.getAttribute('data-move'));
  });

  // Tap physical active card as an alternate scan affordance
  document.getElementById('zone-active').addEventListener('click', function () {
    if (view.classList.contains('mode-setup')) scan();
  });
})();
