'use strict';
window.MediBed = (() => {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icons = {phone:'<path d="M7 3H4a1 1 0 0 0-1 1c0 9 8 17 17 17a1 1 0 0 0 1-1v-3l-5-2-2 2a15 15 0 0 1-7-7l2-2-2-5Z"/>',hospital:'<path d="M5 21V5h14v16M3 21h18M10 21v-4h4v4M9 9h6m-3-3v6M8 14h1m6 0h1"/>',pin:'<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z"/><circle cx="12" cy="10" r="2.5"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',truck:'<path d="M3 6h11v12H3Zm11 5h4l3 4v3h-7M6 9v5m-2-2h4"/><circle cx="7" cy="19" r="2"/><circle cx="18" cy="19" r="2"/>'};
  const icon = name => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || ''}</svg>`;
  const date = value => value ? new Date(value).toLocaleString('en-IN', {day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}) : '—';
  const status = value => `<span class="status-pill ${escape(value)}">${escape(value === 'icu' ? 'ICU' : value.charAt(0).toUpperCase() + value.slice(1))}</span>`;
  const empty = (title, message='') => `<div class="empty-state"><h3>${escape(title)}</h3><p>${escape(message)}</p></div>`;
  async function api(url, options = {}) {
    const headers = {'Accept':'application/json', ...(options.headers || {})};
    if (options.method && options.method !== 'GET') {
      headers['X-CSRF-Token'] = $('meta[name="csrf-token"]').content;
      headers['Content-Type'] = 'application/json';
    }
    let response;
    try { response = await fetch(url, {...options, headers, credentials:'same-origin'}); }
    catch { throw new Error('Cannot reach the local server. Check that MediBed is running.'); }
    let payload;
    try { payload = await response.json(); } catch { throw new Error('The server returned an unexpected response.'); }
    if (!response.ok || !payload.ok) {
      const error = new Error(payload.error?.message || 'This action could not be completed.');
      error.status = response.status; throw error;
    }
    if (payload.data?.csrf_token) $('meta[name="csrf-token"]').content = payload.data.csrf_token;
    return payload.data;
  }
  function toast(message, error = false) {
    const element = document.createElement('div'); element.className = 'app-toast' + (error ? ' error' : '');
    const content = document.createElement('span'); content.textContent = message;
    const close = document.createElement('button'); close.textContent = '×'; close.setAttribute('aria-label', 'Dismiss notification'); close.onclick = () => element.remove();
    element.append(content, close); $('#toast-region').append(element);
    setTimeout(() => element.remove(), 6500);
  }
  function formError(form, message='') { const region = $('.form-error', form); if (region) {region.textContent = message; region.hidden = !message;} }
  async function submit(form, action) {
    const button = $('[type="submit"]', form); const oldText = button.innerHTML;
    button.disabled = true; button.textContent = 'Please wait…'; formError(form);
    try { await action(); } catch (error) {if ($('.form-error', form)) formError(form, error.message); else toast(error.message, true);} finally {button.disabled = false; button.innerHTML = oldText;}
  }
  function sync(ok=true) { const el = $('#sync-status'); if (el) {el.classList.toggle('failed', !ok); el.innerHTML = ok ? '<span class="teal-dot"></span> Updated ' + escape(new Date().toLocaleTimeString('en-IN', {hour:'2-digit',minute:'2-digit',second:'2-digit'})) : 'Connection interrupted · retrying';} }
  function poll(fn, milliseconds=5000) {
    let running = false;
    async function refresh() { if (running || document.hidden) return; running = true; try {await fn(); sync(true);} catch (error) {sync(false); if (!poll.reported) {toast(error.message, true); poll.reported = true;}} finally {running = false;} }
    refresh(); const interval = setInterval(refresh, milliseconds);
    document.addEventListener('visibilitychange', () => {if (!document.hidden) refresh();});
    return {refresh, stop:() => clearInterval(interval)};
  }
  function confirmAction(title, message) {
    const dialog = $('#confirm-dialog'); $('#confirm-title').textContent = title; $('#confirm-message').textContent = message;
    dialog.showModal(); return new Promise(resolve => {
      let confirmed = false;
      $('#confirm-yes').onclick = () => {confirmed = true; dialog.close();};
      dialog.addEventListener('close', () => resolve(confirmed), {once:true});
    });
  }
  let notificationSignature = '';
  async function notifications() {
    const data = await api('/api/notifications'); const count = $('#notification-count');
    if (count) {count.textContent = data.unread_count; count.hidden = !data.unread_count;}
    const region = $('#notification-list');
    if (region) {
      const signature = JSON.stringify(data.notifications);
      if (signature !== notificationSignature) {
        notificationSignature = signature;
        region.innerHTML = data.notifications.length ? data.notifications.map(n => `<article class="notification-item ${n.is_read ? 'read' : ''}"><h3>${!n.is_read ? '<span class="teal-dot"></span>' : ''}${escape(n.title)}</h3><p>${escape(n.message)}</p><div class="notification-bottom"><time>${escape(date(n.created_at))}</time>${!n.is_read ? `<button class="text-button" data-read="${n.id}">Mark as read</button>` : '<span class="small muted">Read</span>'}</div></article>`).join('') : empty('All caught up.', 'Updates about your workspace requests will appear here.');
      }
    }
    return data;
  }
  function drawHistory(canvasId, fallbackId, forecast) {
    const canvas = $('#' + canvasId), fallback = $('#' + fallbackId); if (!canvas) return;
    const history = forecast.history;
    if(!forecast.forecast_available){canvas.hidden=true;fallback.hidden=false;fallback.innerHTML=empty('History is not ready yet.','At least seven recent recorded days are required. No forecast has been invented.');return;}
    const labels = [...history.map(r => r.date), forecast.forecast_date];
    const actual = [...history.map(r => r.available), null];
    const prediction = labels.map(() => null);
    if (history.length) prediction[history.length - 1] = history.at(-1).available;
    prediction[prediction.length - 1] = forecast.predicted_available;
    if (window.Chart) {
      canvas.hidden = false; fallback.hidden = true;
      const existing = Chart.getChart(canvas); if (existing) existing.destroy();
      const historyLabel = forecast.data_source === 'synthetic_kaggle' ? 'Synthetic demo history' : 'Workspace history';
      new Chart(canvas, {type:'line', data:{labels, datasets:[{label:historyLabel, data:actual, borderColor:'#4c9880', backgroundColor:'#4c988010', fill:true, tension:.3, pointRadius:1, borderWidth:2}, {label:'Next-day estimate', data:prediction, borderColor:'#7699bf', borderDash:[5,4], pointRadius:4, borderWidth:2}]}, options:{responsive:true, maintainAspectRatio:false, animation:false, interaction:{mode:'index', intersect:false}, plugins:{legend:{position:'bottom',labels:{usePointStyle:true,boxWidth:7,font:{size:10},padding:20}}}, scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8,font:{size:9},callback:function(v){return this.getLabelForValue(v).slice(5);}}},y:{beginAtZero:true,suggestedMax:forecast.capacity,ticks:{precision:0,font:{size:9}},grid:{color:'#edf2ed'}}}}});
    } else {
      canvas.hidden = true; fallback.hidden = false;
      const values = [...history.map(r => r.available), forecast.predicted_available];
      const max = Math.max(forecast.capacity, ...values, 1);
      const xy = values.map((v,i) => [40+i*720/Math.max(values.length-1,1), 230-v/max*200]);
      const points = xy.map(p => p.join(',')).join(' ');
      fallback.innerHTML = `<svg class="svg-chart" viewBox="0 0 800 270" role="img" aria-label="Recorded workspace history with next-day estimate"><path d="M40 25v205h720" fill="none" stroke="#d5e2d8"/><polyline points="${points}" fill="none" stroke="#4c9880" stroke-width="2.5"/><circle cx="${xy.at(-1)[0]}" cy="${xy.at(-1)[1]}" r="5" fill="#7699bf"/><text x="8" y="32" font-size="11" fill="#84958d">${max}</text><text x="20" y="233" font-size="11" fill="#84958d">0</text><text x="40" y="255" font-size="10" fill="#84958d">${escape(labels[0])}</text><text x="650" y="255" font-size="10" fill="#84958d">${escape(forecast.forecast_date)}</text></svg>`;
      fallback.style.height = '100%';
    }
  }
  function forecastSummary(f) {
    if(!f.forecast_available) return '<div class="forecast-unavailable">'+empty('Forecast not available yet.','At least seven recent recorded days are needed. No hospital-reported prediction is available.')+'</div>';
    const synthetic = f.data_source === 'synthetic_kaggle';
    const source = synthetic ? 'Synthetic Kaggle demo data · not verified' : 'Workspace data · not verified';
    return `<div class="forecast-stat"><span>${source}</span><strong>${f.current_available}<em> beds</em></strong><small>Current editable inventory</small></div><div class="forecast-stat highlight"><span>Experimental next-day estimate</span><strong>${f.predicted_available}<em> beds</em></strong><small>For ${escape(f.forecast_date)} · ${synthetic?'synthetic demo history':'recorded workspace history'}</small></div><div class="forecast-stat"><span>Recorded category capacity</span><strong>${f.capacity}<em> beds</em></strong><small>Bounded from 0 to ${f.capacity}</small></div>`;
  }
  document.addEventListener('click', async event => {
    const close = event.target.closest('[data-close]'); if (close) close.closest('dialog').close();
    const logout = event.target.closest('#logout,[data-logout]');
    if (logout) {try {await api('/api/auth/logout',{method:'POST',body:'{}'}); window.location.href='/';} catch(error){toast(error.message,true);}}
    const read = event.target.closest('[data-read]'); if (read) {try{await api(`/api/notifications/${read.dataset.read}/read`,{method:'POST',body:'{}'}); await notifications();} catch(error){toast(error.message,true);}}
  });
  $('#nav-toggle')?.addEventListener('click', () => {const nav=$('#main-nav'); nav.classList.toggle('open'); $('#nav-toggle').setAttribute('aria-expanded',nav.classList.contains('open'));});
  const auth = $('#auth-form'); if (auth) auth.addEventListener('submit', event => {event.preventDefault(); submit(auth, async () => {const payload = Object.fromEntries(new FormData(auth)); if(auth.dataset.mode === 'register') payload.accept_privacy = auth.elements.accept_privacy.checked; const result=await api('/api/auth/'+auth.dataset.mode,{method:'POST',body:JSON.stringify(payload)}); window.location.href=result.user.role === 'hospital_admin' ? '/admin' : '/patient';});});
  if ($('meta[name="user-role"]').content) poll(notifications);
  return {$,$$,escape,icon,date,status,empty,api,toast,submit,formError,sync,poll,confirmAction,notifications,drawHistory,forecastSummary};
})();
