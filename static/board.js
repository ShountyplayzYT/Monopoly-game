// store the last game info we got from the computer
let ST = null; 
// remember which pop-up is open so we don't open it twice
let modalOpenFor = null; 
// store which player seat is ours
let MY_SEAT = null; 
// timer to check for updates
let pollTimer = null; 

// default colors for property groups if the server doesn't send them
const GROUP_COLORS_FALLBACK = {
  brown:'#955436', lightblue:'#AAE0FA', pink:'#D93A96', orange:'#F7941D',
  red:'#ED1B24', yellow:'#FEF200', green:'#1FB25A', blue:'#0072BB'
};

// send data to the server and get a reply back
async function postJSON(url, body){
  const res = await fetch(url, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body||{})
  });
  const data = await res.json();
  if(data.error){ alert(data.error); throw new Error(data.error); }
  return data;
}

// update our game with new info from the server and redraw everything
function applyState(state){
  ST = state;
  MY_SEAT = state.my_seat;
  renderBoard();
  renderAll();
  checkAutoModals();
}

// get names and money ready, then start the game
async function startGame(){
  const names = [
    document.getElementById('n0').value || "player 1",
    document.getElementById('n1').value || "player 2",
    document.getElementById('n2').value || "player 3",
    document.getElementById('n3').value || "player 4"
  ];
  const ai = [
    document.getElementById('ai0').checked,
    document.getElementById('ai1').checked,
    document.getElementById('ai2').checked,
    document.getElementById('ai3').checked
  ];
  const startMoney = parseInt(document.getElementById('setStartMoney').value) || 1500;
  const data = await postJSON('/api/start', {names, ai_flags: ai, start_money: startMoney});
  document.getElementById('startScreen').style.display = 'none';
  applyState(data);
  startPolling();
}

// roll the dice
async function rollDice(){ const d = await postJSON('/api/roll', {}); applyState(d); }
// pay money to get out of jail
async function payJailFee(){ const d = await postJSON('/api/pay_jail_fee', {}); applyState(d); }
// use a free jail card
async function useGoojf(){ const d = await postJSON('/api/use_goojf', {}); applyState(d); }
// buy a property you landed on
async function buyProperty(){ const d = await postJSON('/api/buy', {}); applyState(d); }
// pass on buying a property
async function declineProperty(){ const d = await postJSON('/api/decline', {}); applyState(d); }
// finish your turn
async function endTurn(){ const d = await postJSON('/api/end_turn', {}); applyState(d); }
// build a house on your property
async function buildHouse(id){ const d = await postJSON('/api/build_house', {space_id:id}); applyState(d); }
// sell a house back to the bank
async function sellHouse(id){ const d = await postJSON('/api/sell_house', {space_id:id}); applyState(d); }
// mortgage your property for quick cash
async function mortgage(id){ const d = await postJSON('/api/mortgage', {space_id:id}); applyState(d); }
// pay back your mortgage to use the property again
async function unmortgage(id){ const d = await postJSON('/api/unmortgage', {space_id:id}); applyState(d); }
// offer money in an auction
async function auctionBid(amount){ const d = await postJSON('/api/auction_bid', {amount}); applyState(d); }
// give up on bidding in an auction
async function auctionFold(){ const d = await postJSON('/api/auction_fold', {}); applyState(d); }
// say yes or no to a trade offer
async function respondTrade(accept){ const d = await postJSON('/api/respond_trade', {accept}); applyState(d); }

// save the game progress
async function saveGame(){ await postJSON('/api/save', {}); alert('game saved.'); }
// load a saved game back up
async function loadGame(){
  try{
    const d = await postJSON('/api/load', {});
    document.getElementById('startScreen').style.display = 'none';
    applyState(d);
  }catch(e){}
}

// figure out where each square goes on the game grid
function gridPos(i){
  if(i===0) return {row:11,col:11};
  if(i>=1&&i<=9) return {row:11,col:11-i};
  if(i===10) return {row:11,col:1};
  if(i>=11&&i<=19) return {row:21-i,col:1};
  if(i===20) return {row:1,col:1};
  if(i>=21&&i<=29) return {row:1,col:i-19};
  if(i===30) return {row:1,col:11};
  if(i>=31&&i<=39) return {row:i-29,col:11};
}

// pick the right picture for special board spaces
function getSpaceImageHTML(index){
  let imgUrl = "";
  switch(index){
    case 0:  imgUrl = "GO.png"; break;
    case 2:  imgUrl = "Chest.png"; break;
    case 5:  imgUrl = "railroad.png"; break;
    case 15: imgUrl = "railroad.png"; break;
    case 17: imgUrl = "Chest.png"; break;
    case 25: imgUrl = "railroad.png"; break;
    case 35: imgUrl = "railroad.png"; break;
    case 33: imgUrl = "Chest.png"; break;
    case 4:  imgUrl = "Taxbig.png"; break;
    case 7:  imgUrl = "PinkQ.png"; break;
    case 10: imgUrl = "in_jail.png"; break;
    case 12: imgUrl = "Bulb.png"; break;
    case 20: imgUrl = "Car.png"; break;
    case 22: imgUrl = "BlueQ.png"; break;
    case 28: imgUrl = "Faucet.png"; break;
    case 30: imgUrl = "GotoJail.png"; break;
    case 36: imgUrl = "OrangeQ.png"; break;
    case 38: imgUrl = "Taxring.png"; break;
  }
  if(imgUrl) return `<img src="/static/${imgUrl}" class="space-icon">`;
  return "";
}

// draw the game board squares on the screen
let boardBuilt = false;
function renderBoard(){
  if(boardBuilt) return; 
  boardBuilt = true;
  const board = document.getElementById('board');
  board.innerHTML = '';
  const GC = (ST && ST.group_colors) || GROUP_COLORS_FALLBACK;
  ST.spaces.forEach((s,i)=>{
    const {row,col} = gridPos(i);
    const div = document.createElement('div');
    div.id = 'space'+i;
    div.style.gridRow = row; div.style.gridColumn = col;
    const isCorner = (i===0||i===10||i===20||i===30);
    div.className = 'space'+(isCorner?' corner':'');
    div.onclick = ()=>showPropertyInfo(i);
    const spaceImage = getSpaceImageHTML(i);
    if(isCorner){
      div.innerHTML = '<div></div>'+spaceImage+'<div style="font-size:8px;">'+s.name+'</div><div class="tokens" id="tok'+i+'"></div>';
    } else {
      let bar='';
      if(s.type==='property') bar='<div class="colorbar" style="background:'+GC[s.group]+'"></div>';
      let priceLine='';
      if(s.type==='property'||s.type==='railroad'||s.type==='utility') priceLine='<div class="pr">$'+s.price+'</div>';
      if(s.type==='tax') priceLine='<div class="pr">pay $'+s.amount+'</div>';
      div.innerHTML = bar+
        '<div class="houses" id="houses'+i+'"></div>'+
        spaceImage+
        '<div class="nm">'+s.name+'</div>'+priceLine+
        '<div class="ownerBar" id="ownerbar'+i+'"></div>'+
        '<div class="tokens" id="tok'+i+'"></div>';
    }
    board.appendChild(div);
  });
  const center = document.createElement('div');
  center.id = 'center';
  center.innerHTML =
    '<div id="deckRow">'+
      '<div class="deckCard chance">chance</div>'+
      '<div id="logoTitle">mono<span>poly</span></div>'+
      '<div class="deckCard chest">chest</div>'+
    '</div>'+
    '<div id="turnBanner"></div>'+
    '<div id="diceArea"></div>'+
    '<div id="actionBtns"></div>'+
    '<div id="miniLog"></div>';
  board.appendChild(center);
}

// update all parts of the game screen
function renderAll(){
  renderTokensAndHouses();
  renderPlayersPanel();
  renderPropsPanel();
  renderActionBtns();
  showTurnBanner();
  renderLog();
  const totalHouses = ST.spaces.reduce((t,s)=> (s.houses>0&&s.houses<5)?t+s.houses:t,0);
  const totalHotels = ST.spaces.reduce((t,s)=> s.houses===5?t+1:t,0);
  document.getElementById('bankInfo').textContent =
    'bank: $'+ST.bank_money+' | houses left: '+(32-totalHouses)+' | hotels left: '+(12-totalHotels);
}

// show the history text log at the bottom
function renderLog(){
  const el = document.getElementById('log');
  el.innerHTML = '';
  (ST.log||[]).forEach(msg=>{
    const d = document.createElement('div');
    d.textContent = msg;
    el.appendChild(d);
  });
  document.getElementById('miniLog').textContent = (ST.log && ST.log[0]) || '';
}

// check if a player owns all properties in a color group
function ownsFullGroup(p, group){
  return ST.spaces.filter(s=>s.group===group).every(s=>s.owner===p.id);
}

// make sure houses are built evenly across properties
function evenBuildOk(space, mode){
  const gs = ST.spaces.filter(s=>s.group===space.group);
  const min = Math.min(...gs.map(s=>s.houses));
  const max = Math.max(...gs.map(s=>s.houses));
  return mode==='build' ? space.houses===min : space.houses===max;
}

// draw player game pieces and houses on the board squares
function renderTokensAndHouses(){
  const GC = ST.group_colors || GROUP_COLORS_FALLBACK;
  ST.spaces.forEach((s,i)=>{
    const tokEl = document.getElementById('tok'+i);
    tokEl.innerHTML = '';
    ST.players.forEach(p=>{
      if(!p.bankrupt && p.pos===i){
        const t = document.createElement('div');
        t.className = 'token'; t.style.background = p.color; t.title = p.name;
        tokEl.appendChild(t);
      }
    });
    if(s.type==='property'){
      const hEl = document.getElementById('houses'+i);
      hEl.innerHTML = '';
      if(s.houses===5){ const h=document.createElement('div'); h.className='hotel'; hEl.appendChild(h); }
      else if(s.houses>0){ for(let k=0;k<s.houses;k++){ const h=document.createElement('div'); h.className='house'; hEl.appendChild(h);} }
      const spaceEl = document.getElementById('space'+i);
      spaceEl.classList.toggle('mortgaged', !!s.mortgaged);
      const glow = s.owner!==null && ownsFullGroup(ST.players[s.owner], s.group);
      spaceEl.classList.toggle('monopolyGlow', !!glow);
    }
    if(s.type==='property'||s.type==='railroad'||s.type==='utility'){
      const bar = document.getElementById('ownerbar'+i);
      if(bar){
        if(s.owner!==null){ bar.style.background = ST.players[s.owner].color; bar.style.opacity = s.mortgaged?0.4:1; }
        else { bar.style.background = 'transparent'; }
      }
    }
  });
}

// show the list of players and their money
function renderPlayersPanel(){
  const box = document.getElementById('playersBox');
  box.innerHTML = '';
  ST.players.forEach((p, idx)=>{
    const row = document.createElement('div');
    row.className = 'playerRow'+(idx===ST.current_index && !p.bankrupt?' active':'')+(p.bankrupt?' bankrupt':'');
    row.innerHTML = '<div class="dot" style="background:'+p.color+'"></div>'+
      '<div style="flex:1">'+p.name+(p.is_ai?' \u{1F916}':'')+(p.in_jail?' (in jail)':'')+'</div>'+
      '<div>$'+p.money+'</div>'+
      (!p.bankrupt ? '<button class="small" onclick="openTradeModal('+p.id+')">trade</button>' : '');
    box.appendChild(row);
  });
}

// calculate how much a property is worth
function propValue(s){
  let v = s.price||0;
  if(s.houses>0) v += s.houses*s.houseCost;
  if(s.mortgaged) v -= s.mortgageValue;
  return v;
}

// show all properties owned by each player
function renderPropsPanel(){
  const GC = ST.group_colors || GROUP_COLORS_FALLBACK;
  const box = document.getElementById('propsList');
  box.innerHTML = '';
  ST.players.forEach(p=>{
    const owned = ST.spaces.filter(s=>s.owner===p.id);
    const header = document.createElement('div');
    header.className = 'pgHeader';
    header.innerHTML = '<div class="dot" style="background:'+p.color+'"></div>'+p.name+(p.bankrupt?' (out)':'')+' — $'+p.money+(p.goojf.length?' | cards x'+p.goojf.length:'');
    box.appendChild(header);
    if(owned.length===0){
      const e = document.createElement('div');
      e.style.cssText = 'font-size:11px;color:#777;margin:0 0 4px 16px;';
      e.textContent = 'no properties.';
      box.appendChild(e);
      return;
    }
    owned.forEach(s=>{
      const row = document.createElement('div'); row.className = 'propRow';
      const isMono = s.type==='property' && ownsFullGroup(p, s.group);
      if(isMono) row.classList.add('monopolyRow');
      const swatch = s.type==='property' ? GC[s.group] : (s.type==='railroad' ? '#000' : '#888');
      let marks = '';
      if(s.type==='property'){
        if(s.houses===5) marks = '<span class="mark hotel">&#9679;</span>';
        else if(s.houses>0) marks = '<span class="mark house">'+('&#9679;').repeat(s.houses)+'</span>';
        else marks = '<span class="mark zero">0</span>';
      }
      row.innerHTML = '<div class="swatch" style="background:'+swatch+'"></div>'+
        '<div class="pname">'+s.name+(s.mortgaged?' \u{1F512}':'')+'</div>'+
        '<div class="marks">'+marks+'</div>';
      let extra = '<button class="small" onclick="showPropertyInfo('+s.id+')">i</button>';
      if(!p.bankrupt && !p.is_ai && p.id === MY_SEAT){
        if(s.type==='property'){
          const fullGroup = ownsFullGroup(p, s.group);
          const canBuild = fullGroup && !s.mortgaged && s.houses<5 && evenBuildOk(s,'build');
          const canSell = s.houses>0 && evenBuildOk(s,'sell');
          extra += '<button class="small" '+(canBuild?'':'disabled')+' onclick="buildHouse('+s.id+')">+</button>';
          extra += '<button class="small" '+(canSell?'':'disabled')+' onclick="sellHouse('+s.id+')">-</button>';
        }
        const canMortgage = s.houses===0 && !s.mortgaged;
        if(canMortgage) extra += '<button class="small" onclick="mortgage('+s.id+')">m</button>';
        if(s.mortgaged) extra += '<button class="small" onclick="unmortgage('+s.id+')">u</button>';
      }
      row.innerHTML += extra;
      box.appendChild(row);
    });
  });
}

// show whose turn it is at the top banner
function showTurnBanner(){
  const p = ST.players[ST.current_index];
  document.getElementById('turnBanner').textContent = ST.turn_phase==='game_over' ? "game over" : (p ? p.name+"'s turn — $"+p.money : '');
}

// helper to make buttons easily
function mkBtn(label, fn, disabled){
  const b = document.createElement('button');
  b.textContent = label; b.disabled = !!disabled; b.onclick = fn;
  return b;
}

// show the correct buttons for what you can do right now
function renderActionBtns(){
  const box = document.getElementById('actionBtns');
  box.innerHTML = '';
  if(ST.turn_phase==='game_over'){ box.innerHTML = '<b>game over!</b>'; return; }
  const p = ST.players[ST.current_index];
  if(!p || p.bankrupt) return;
  if(p.is_ai){ box.innerHTML = '<i>computer is playing…</i>'; return; }

  if(MY_SEAT !== null && p.id !== MY_SEAT){
    box.innerHTML = '<i>waiting for '+p.name+'…</i>';
    return;
  }

  if(['awaiting_buy','awaiting_auction','awaiting_trade'].includes(ST.turn_phase) || ST.trade){
    box.innerHTML = '<i>finish the pop-up to continue…</i>'; return;
  }
  if(ST.turn_phase==='must_end_turn'){
    const b = mkBtn('end turn →', endTurn, false);
    b.classList.add('primary');
    box.appendChild(b);
    return;
  }
  box.appendChild(mkBtn('trade', ()=>openTradeModal(p.id), false));
  if(p.in_jail){
    box.appendChild(mkBtn('pay $50 and roll', payJailFee, p.money<50));
    box.appendChild(mkBtn('use free jail card', useGoojf, p.goojf.length===0));
    box.appendChild(mkBtn('roll for doubles', rollDice, false));
    return;
  }
  const rollBtn = mkBtn('roll dice', rollDice, false);
  rollBtn.classList.add('primary');
  box.appendChild(rollBtn);
}

// open a pop-up window on the screen
function openModal(opts){
  const overlay = document.getElementById('overlay');
  const modal = document.getElementById('modal');
  modal.className = opts.cardClass ? 'cardModal '+opts.cardClass : '';
  modal.innerHTML = '<h2>'+opts.title+'</h2><div>'+opts.body+'</div><div class="modalBtns"></div>';
  const btnBox = modal.querySelector('.modalBtns');
  (opts.buttons||[]).forEach(b=>{
    const el = document.createElement('button');
    el.textContent = b.label; el.disabled = !!b.disabled;
    el.className = b.label.startsWith('buy') ? 'gold' : '';
    el.onclick = b.action;
    btnBox.appendChild(el);
  });
  overlay.style.display = 'flex';
}

// close the pop-up window
function closeModal(){
  document.getElementById('overlay').style.display = 'none';
  modalOpenFor = null;
}

// check if we need to automatically pop up a window for the player
function checkAutoModals(){
  if(!ST) return;
  const p = ST.players[ST.current_index];
  if(!p) return;

  if(ST.trade && ST.trade.to_id === MY_SEAT){
    const key = 'trade';
    if(modalOpenFor!==key){ modalOpenFor=key; openTradeResponseModal(ST.trade); }
    return;
  }
  if(ST.turn_phase==='awaiting_buy' && ST.pending && !p.is_ai && p.id === MY_SEAT){
    const key = 'buy'+ST.pending.space_id;
    if(modalOpenFor!==key){ modalOpenFor=key; openBuyModal(p, ST.pending); }
    return;
  }
  if(ST.turn_phase==='awaiting_auction' && ST.auction){
    const bidder = ST.players[ST.auction.bidders[ST.auction.turn_index]];
    if(!bidder.is_ai && bidder.id === MY_SEAT){
      const key = 'auction'+ST.auction.space_id+'_'+ST.auction.current_bid;
      if(modalOpenFor!==key){ modalOpenFor=key; openAuctionModal(bidder); }
      return;
    }
  }
}

// pop-up to buy a property
function openBuyModal(p, pending){
  const space = ST.spaces[pending.space_id];
  openModal({
    title: "buy property?",
    body: space.name+" is not owned yet.<br>price: $"+space.price+"<br>your cash: $"+p.money,
    buttons: [
      {label:"buy for $"+space.price, action: async ()=>{ closeModal(); await buyProperty(); }, disabled: p.money<space.price},
      {label:"decline", action: async ()=>{ closeModal(); await declineProperty(); }}
    ]
  });
}

// pop-up for bidding in an auction
function openAuctionModal(activePlayer){
  const a = ST.auction;
  const space = ST.spaces[a.space_id];
  const highestName = a.highest_bidder!==null ? ST.players[a.highest_bidder].name : '';
  openModal({
    title: "auction: "+space.name,
    body:
      "<b>highest bid so far:</b> $"+a.current_bid+" "+(highestName?'('+highestName+')':'')+"<br><br>"+
      '<div style="padding:10px; border:2px solid #333; border-radius:6px;">'+
        "<h3>"+activePlayer.name+"'s bid</h3>"+
        "your cash: $"+activePlayer.money+"<br><br>"+
        'bid amount: $<input type="number" id="auctionBidInput" value="'+(a.current_bid+1)+'" min="'+(a.current_bid+1)+'" max="'+activePlayer.money+'" style="width:80px; padding:4px;">'+
      '</div>',
    buttons: [
      {label:"place bid", action: async ()=>{
        const amt = parseInt(document.getElementById('auctionBidInput').value);
        closeModal(); await auctionBid(amt); 
      }},
      {label:"fold", action: async ()=>{ closeModal(); await auctionFold(); }}
    ]
  });
}

// show details when you click on a property on the board
function showPropertyInfo(id){
  const s = ST.spaces[id];
  const GC = ST.group_colors || GROUP_COLORS_FALLBACK;
  if(['go','jail','free','gotojail','chance','community'].includes(s.type)){
    openModal({title:s.name, body:'no info to buy here.', buttons:[{label:'close', action:closeModal}]});
    return;
  }
  let rows = '';
  if(s.type==='property'){
    rows = '<tr><td>group</td><td style="background:'+GC[s.group]+'">&nbsp;</td></tr>'+
      '<tr><td>purchase price</td><td>$'+s.price+'</td></tr>'+
      '<tr><td>mortgage value</td><td>$'+s.mortgageValue+'</td></tr>'+
      '<tr><td>house cost</td><td>$'+s.houseCost+'</td></tr>'+
      '<tr><td>rent (no houses)</td><td>$'+s.rent[0]+'</td></tr>'+
      '<tr><td>rent (1 house)</td><td>$'+s.rent[1]+'</td></tr>'+
      '<tr><td>rent (2 houses)</td><td>$'+s.rent[2]+'</td></tr>'+
      '<tr><td>rent (3 houses)</td><td>$'+s.rent[3]+'</td></tr>'+
      '<tr><td>rent (4 houses)</td><td>$'+s.rent[4]+'</td></tr>'+
      '<tr><td>rent (hotel)</td><td>$'+s.rent[5]+'</td></tr>';
  } else if(s.type==='railroad'){
    rows = '<tr><td>purchase price</td><td>$'+s.price+'</td></tr>'+
      '<tr><td>mortgage value</td><td>$'+s.mortgageValue+'</td></tr>'+
      '<tr><td>rent (1 owned)</td><td>$25</td></tr><tr><td>rent (2 owned)</td><td>$50</td></tr>'+
      '<tr><td>rent (3 owned)</td><td>$100</td></tr><tr><td>rent (4 owned)</td><td>$200</td></tr>';
  } else if(s.type==='utility'){
    rows = '<tr><td>purchase price</td><td>$'+s.price+'</td></tr>'+
      '<tr><td>mortgage value</td><td>$'+s.mortgageValue+'</td></tr>'+
      '<tr><td>rent (1 owned)</td><td>4x dice</td></tr><tr><td>rent (2 owned)</td><td>10x dice</td></tr>';
  }
  rows += '<tr><td>current owner</td><td>'+(s.owner!==null ? ST.players[s.owner].name : 'bank / unowned')+'</td></tr>';
  if(s.owner!==null){
    rows += '<tr><td>mortgaged</td><td>'+(s.mortgaged?'yes':'no')+'</td></tr>'+
      '<tr><td>houses/hotel</td><td>'+(s.type==='property' ? (s.houses===5?'hotel':s.houses+' house(s)') : '—')+'</td></tr>';
  }
  rows += '<tr><td>times landed on</td><td>'+((ST.stats.landings && ST.stats.landings[s.id]) || 0)+'</td></tr>';
  openModal({title: s.name, body: '<table class="infoTable">'+rows+'</table>', buttons:[{label:'close', action:closeModal}]});
}

// open the window to trade with another player
function openTradeModal(initiatorId, prefill){
  const p = ST.players[initiatorId];
  const partners = ST.players.filter(o=>o.id!==p.id && !o.bankrupt);
  if(partners.length===0){ alert("no other players to trade with."); return; }
  let partnerOptions = partners.map(o=>'<option value="'+o.id+'" '+(prefill&&prefill.partnerId===o.id?'selected':'')+'>'+o.name+' ($'+o.money+')</option>').join('');

  openModal({
    title: "propose trade",
    body:
      '<label>you are: <b>'+p.name+'</b></label><br>'+
      '<label>trade with:</label>'+
      '<select id="tradePartnerSelect" class="trade-select" onchange="updateTradePartnerProps()">'+partnerOptions+'</select>'+
      '<label>message (optional):</label>'+
      '<input type="text" id="tradeMessageInput" class="trade-select">'+
      '<div style="display:flex; gap:10px;">'+
        '<div style="flex:1;"><strong>you give:</strong>'+
          '<div id="givePropsList" class="trade-props-box"></div>'+
          '<div id="giveGoojfList" class="trade-props-box"></div>'+
          '<div class="trade-row"><label>cash ($):</label><input type="number" id="giveCashInput" value="0" min="0" max="'+p.money+'"></div>'+
        '</div>'+
        '<div style="flex:1;"><strong>you want:</strong>'+
          '<div id="getPropsList" class="trade-props-box"></div>'+
          '<div id="getGoojfList" class="trade-props-box"></div>'+
          '<div class="trade-row"><label>cash ($):</label><input type="number" id="getCashInput" value="0" min="0"></div>'+
        '</div>'+
      '</div>',
    buttons: [
      {label:"propose trade", action: ()=>submitTradeOffer(p.id)},
      {label:"cancel", action: closeModal}
    ]
  });

  const myProps = ST.spaces.filter(s=>s.owner===p.id);
  document.getElementById('givePropsList').innerHTML = myProps.length>0
    ? myProps.map(s=>'<label><input type="checkbox" class="give-prop-chk" value="'+s.id+'"> '+s.name+(s.mortgaged?' (mortgaged)':'')+'</label>').join('')
    : '<i>no properties</i>';
  document.getElementById('giveGoojfList').innerHTML = p.goojf.length>0
    ? '<label><input type="checkbox" id="give-goojf-chk"> free jail card</label>' : '<i>no jail cards</i>';

  updateTradePartnerProps();
}

// update the partner's property list when you change who you trade with
function updateTradePartnerProps(){
  const partnerId = parseInt(document.getElementById('tradePartnerSelect').value);
  const partner = ST.players[partnerId];
  const partnerProps = ST.spaces.filter(s=>s.owner===partnerId);
  document.getElementById('getPropsList').innerHTML = partnerProps.length>0
    ? partnerProps.map(s=>'<label><input type="checkbox" class="get-prop-chk" value="'+s.id+'"> '+s.name+(s.mortgaged?' (mortgaged)':'')+'</label>').join('')
    : '<i>no properties</i>';
  document.getElementById('getGoojfList').innerHTML = partner.goojf.length>0
    ? '<label><input type="checkbox" id="get-goojf-chk"> free jail card</label>' : '<i>no jail cards</i>';
}

// send the trade offer to the server
async function submitTradeOffer(initiatorId){
  const partnerId = parseInt(document.getElementById('tradePartnerSelect').value);
  const givePropIds = Array.from(document.querySelectorAll('.give-prop-chk:checked')).map(el=>parseInt(el.value));
  const getPropIds = Array.from(document.querySelectorAll('.get-prop-chk:checked')).map(el=>parseInt(el.value));
  const giveCash = parseInt(document.getElementById('giveCashInput').value) || 0;
  const getCash = parseInt(document.getElementById('getCashInput').value) || 0;
  const giveGoojfEl = document.getElementById('give-goojf-chk');
  const getGoojfEl = document.getElementById('get-goojf-chk');
  const giveGoojf = giveGoojfEl ? giveGoojfEl.checked : false;
  const getGoojf = getGoojfEl ? getGoojfEl.checked : false;
  const message = document.getElementById('tradeMessageInput').value.trim();

  closeModal();
  const data = await postJSON('/api/propose_trade', {
    from_id: initiatorId, to_id: partnerId,
    give_props: givePropIds, give_cash: giveCash, give_goojf: giveGoojf,
    get_props: getPropIds, get_cash: getCash, get_goojf: getGoojf,
    message
  });
  applyState(data.state);
  if(data.result==='accept') alert('trade accepted!');
  else if(data.result==='reject') alert('trade rejected.');
}

// pop-up when someone sends you a trade offer
function openTradeResponseModal(trade){
  const from = ST.players[trade.from_id];
  const to = ST.players[trade.to_id];
  const givePropNames = trade.give_props.length ? trade.give_props.map(id=>ST.spaces[id].name).join(', ') : '—';
  const getPropNames = trade.get_props.length ? trade.get_props.map(id=>ST.spaces[id].name).join(', ') : '—';
  openModal({
    title: "trade offer from "+from.name,
    body:
      (trade.message ? '<div style="background:#eee; padding:8px; font-style:italic; margin-bottom:10px;">"'+trade.message+'"</div>' : '')+
      '<b>'+to.name+' gets:</b> '+givePropNames+' + $'+trade.give_cash+(trade.give_goojf?' + card':'')+'<br>'+
      '<b>'+to.name+' gives:</b> '+getPropNames+' + $'+trade.get_cash+(trade.get_goojf?' + card':''),
    buttons: [
      {label:"accept trade", action: async ()=>{ closeModal(); await respondTrade(true); }},
      {label:"reject", action: async ()=>{ closeModal(); await respondTrade(false); }}
    ]
  });
}

// show game statistics in a window
function showStats(){
  if(!ST) return;
  const landings = ST.stats.landings || {};
  const mostLanded = Object.entries(landings).sort((a,b)=>b[1]-a[1]).slice(0,5)
    .map(e=>ST.spaces[e[0]].name+': '+e[1]).join('<br>') || 'no data yet';
  const rows = ST.players.map(p=>'<tr><td>'+p.name+'</td><td>$'+((ST.stats.earned&&ST.stats.earned[p.id])||0)+'</td><td>$'+((ST.stats.rentPaid&&ST.stats.rentPaid[p.id])||0)+'</td></tr>').join('');
  openModal({
    title:"game statistics",
    body:
      '<table class="infoTable">'+
        '<tr><td><b>turns played</b></td><td>'+ST.stats.turns+'</td></tr>'+
        '<tr><td><b>total trades</b></td><td>'+ST.stats.trades+'</td></tr>'+
      '</table>'+
      '<br><b>per player:</b>'+
      '<table class="infoTable"><tr><td><b>player</b></td><td><b>earned</b></td><td><b>rent paid</b></td></tr>'+rows+'</table>'+
      '<br><b>most visited spaces:</b><br>'+mostLanded,
    buttons:[{label:'close', action:closeModal}]
  });
}

// create a new online room
async function createRoom(){
  const data = await postJSON('/api/create_room', {});
  MY_SEAT = data.seat;
  document.getElementById('roomCodeText').textContent = data.room_code;
  document.getElementById('roomCodeDisplay').style.display = 'block';
  startPolling(); 
}

// join an existing room with a code
async function joinRoom(){
  const code = document.getElementById('joinCodeInput').value.trim().toUpperCase();
  if(!code){ alert('enter a room code.'); return; }
  const data = await postJSON('/api/join_room', {room_code: code});
  MY_SEAT = data.seat;
  document.getElementById('roomCodeText').textContent = data.room_code;
  document.getElementById('roomCodeDisplay').style.display = 'block';
  document.getElementById('joinCodeInput').disabled = true;
  startPolling();
}

// check room updates while waiting in the lobby
async function refreshRoomInfo(){
  try{
    const res = await fetch('/api/room_info');
    const info = await res.json();
    if(info.error) return;
    if(info.started){
      document.getElementById('roomScreen').style.display = 'none';
      document.getElementById('startScreen').style.display = 'none';
      const state = await (await fetch('/api/state')).json();
      applyState(state);
      return;
    }
    document.getElementById('waitingInfo').textContent =
      info.seat_count + ' player(s) in room. waiting for host to start…';
  }catch(e){ }
}

// show the start screen from the lobby
function showStartScreenFromLobby(){
  document.getElementById('roomScreen').style.display = 'none';
  document.getElementById('startScreen').style.display = 'flex';
}

// check for updates from the server regularly
function startPolling(){
  if(pollTimer) return; 
  pollTimer = setInterval(async ()=>{
    try{
      if(!ST || !ST.started){
        await refreshRoomInfo();
        return;
      }
      const res = await fetch('/api/state');
      const data = await res.json();
      if(data.error) return;
      applyState(data);
    }catch(e){ }
  }, 2000);
}

// play locally on one computer
async function playLocally(){
  await postJSON('/api/start_local', {});
  document.getElementById('roomScreen').style.display = 'none';
  document.getElementById('startScreen').style.display = 'flex';
}