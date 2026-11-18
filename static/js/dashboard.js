'use strict';
(() => {
  const {$,$$,escape:e,icon,date,status,empty,api,toast,submit,poll,confirmAction,notifications,drawHistory,forecastSummary} = MediBed;
  const page = document.body.dataset.page;
  const query = form => new URLSearchParams(new FormData(form));
  const checkedDate = value => value ? new Date(value).toLocaleDateString('en-IN', {day:'numeric',month:'short',year:'numeric'}) : 'Not recorded';

  function hospitalCard(h, params) {
    const c = h.inventory, verified = h.operational_verified, synthetic = h.inventory_source === 'synthetic_kaggle';
    let availability = '<div class="unknown-inventory"><strong>Call to confirm availability</strong><p>Hospital inventory is not connected. Bed counts have not been supplied by this hospital.</p></div>';
    if (h.has_inventory) {
      const ratio = c.total ? c.available / c.total * 100 : 0;
      availability = `<div class="availability-head"><span><strong>${c.available}</strong><span class="of-total"> / ${c.total} ${verified?'reported':synthetic?'synthetic demo':'workspace'} beds</span></span><span class="status-pill ${verified?'available':'unknown'}">${verified?'Hospital reported':synthetic?'Synthetic demo · not verified':'Unverified workspace'}</span></div><div class="availability-track"><i style="width:${ratio}%"></i></div><div class="capability-row"><div><b>${c.by_type.icu.available}</b>ICU</div><div><b>${c.oxygen_available}</b>Oxygen capable</div><div><b>${c.ventilator_available}</b>Ventilator capable</div></div><p class="availability-source">${verified?'Confirm directly before travelling.':synthetic?'Illustrative Kaggle-derived data; not supplied by the hospital. Call to confirm actual availability.':'Workspace figures are not hospital capacity or confirmed availability.'}</p>`;
    }
    return `<article class="hospital-card"><div class="hospital-card-top"><span class="hospital-monogram">${icon('hospital')}</span><span class="badge-soft">${h.hospital_type==='government'?'Government':'Non-government'}</span></div><h3>${e(h.name)}</h3><p class="location">${icon('pin')}${e(h.area)}, Pune</p>${availability}<div class="hospital-card-bottom"><span class="updated-label">Directory contact checked: ${e(checkedDate(h.contact_checked_at))}</span><a href="/hospitals/${h.id}?${e(params.toString())}">View details ${icon('arrow')}</a></div></article>`;
  }

  function ambulanceCard(a) {
    return `<article class="hospital-card ambulance-card"><div class="hospital-card-top"><span class="hospital-monogram">${icon('truck')}</span><span class="status-pill ${e(a.status)}">${e(a.availability_label)}</span></div><h3>${e(a.hospital_name)}</h3><p class="location">${icon('pin')}${e(a.area)}, Pune</p><span class="ambulance-type">${e(a.contact_label)}</span><p class="availability-source">${a.status==='unknown'?'No live availability feed. The operator must confirm a vehicle.':e(a.availability_source==='workspace_unverified'?'Unverified workspace report. Call the dispatcher to confirm.':'Reported by the connected hospital. Confirm with the dispatcher.')}</p><span class="call-number">${e(a.phone)}</span><div class="call-actions"><a class="btn btn-primary" href="${e(a.tel_uri)}" aria-label="Call ambulance desk at ${e(a.hospital_name)}">${icon('phone')} Call ambulance desk</a>${a.alternate_tel_uri?`<a class="btn btn-outline-secondary" href="${e(a.alternate_tel_uri)}">Alternate: ${e(a.alternate_phone)}</a>`:''}</div><div class="contact-provenance"><a href="${e(a.source_url)}" target="_blank" rel="noopener noreferrer">Official contact source ↗</a><br><span class="muted">Checked ${e(checkedDate(a.contact_checked_at))}${a.status_updated_at?' · Reported '+e(date(a.status_updated_at)):''}</span></div><p class="small muted mt-3">Call to arrange transport. No dispatch or arrival time is guaranteed by MediBed.</p></article>`;
  }

  if (page === 'search') {
    const form = $('#hospital-search');
    let signature = '', searchVersion = 0;
    const initial = new URLSearchParams(location.search);
    for (const [key,value] of initial) {
      const el = form.elements.namedItem(key);
      if (el) { if (el.type === 'checkbox') el.checked = value === 'true'; else el.value = value; }
    }
    async function refresh() {
      const params = query(form), version = ++searchVersion;
      params.delete('priority');
      const [data,stats] = await Promise.all([api('/api/hospitals?' + params), api('/api/dashboard/stats')]);
      if (version !== searchVersion) return;
      $('#result-count').textContent = data.count;
      $$('[data-stat]').forEach(el => {
        const value = el.dataset.stat === 'icu' ? stats.by_type.icu.available : stats[el.dataset.stat];
        el.textContent = value ?? '—';
      });
      const next = JSON.stringify(data.hospitals) + query(form).toString();
      if (next !== signature) {
        signature = next;
        $('#hospital-results').innerHTML = data.hospitals.length ? data.hospitals.map(h => hospitalCard(h, query(form))).join('') : empty('No recorded matches.', 'Unconnected hospital feeds have unknown availability. Reset the bed filters to browse the Pune directory and call a hospital directly.');
      }
    }
    const updates = poll(refresh);
    form.addEventListener('submit', event => { event.preventDefault(); signature = ''; history.replaceState(null,'','?' + query(form)); updates.refresh(); });
    form.addEventListener('reset', () => setTimeout(() => { signature = ''; history.replaceState(null,'',location.pathname); updates.refresh(); }, 0));
  }

  if (page === 'hospital') {
    const id = $('#hospital-detail').dataset.hospitalId;
    let signature = '';
    poll(async () => {
      const h = await api('/api/hospitals/' + id);
      const next = JSON.stringify(h); if (next === signature) return; signature = next;
      const c = h.inventory;
      $('#detail-inventory').innerHTML = ['general','icu','emergency'].map(kind => {
        const v = c.by_type[kind];
        const source = h.operational_verified ? 'hospital-reported' : h.inventory_source === 'synthetic_kaggle' ? 'synthetic demo' : 'workspace';
        return `<div class="bed-type-card"><span>${kind==='icu'?'ICU':kind.charAt(0).toUpperCase()+kind.slice(1)}</span><strong>${h.has_inventory?v.available:'—'}</strong><small>${h.has_inventory?v.total+' '+source+' beds':'Hospital feed not connected'}</small></div>`;
      }).join('');
      $('#detail-capabilities').innerHTML = h.has_inventory ? `<span><strong>${c.oxygen_available}</strong> oxygen-capable workspace beds</span><span><strong>${c.ventilator_available}</strong> ventilator-capable workspace beds</span>` : '';
      $('#detail-updated').textContent = h.has_inventory ? 'Workspace changed ' + date(h.last_updated) + ' · ' + (h.operational_verified?'Hospital reported':h.inventory_source === 'synthetic_kaggle'?'Synthetic demo; not hospital-reported':'Unverified; not hospital capacity') : 'Hospital capacity and current availability have not been supplied.';
    });
    api('/api/ambulances?hospital_id=' + id).then(data => {
      $('#hospital-ambulance-contacts').innerHTML = data.ambulances.length ? data.ambulances.map(a => `<div class="hospital-contact"><p>${e(a.contact_label)} · <strong>${e(a.phone)}</strong></p><div class="button-row"><a class="btn btn-primary" href="${e(a.tel_uri)}">${icon('phone')} Call ambulance desk</a><a href="${e(a.source_url)}" class="btn btn-outline-secondary" target="_blank" rel="noopener noreferrer">Official source ↗</a></div><p class="small muted mt-3">Availability and arrival time must be confirmed by phone.</p></div>`).join('') : '<p class="muted">A dedicated ambulance number has not been verified for this listing. Call the hospital main line or <a href="tel:112">112 in an emergency</a>.</p>';
    }).catch(error => { $('#hospital-ambulance-contacts').textContent = error.message; });
    api('/api/predictions?hospital_id=' + id).then(f => {
      $('#detail-forecast').innerHTML = f.forecast_available ? `<div class="forecast-mini"><strong>${f.predicted_available}</strong><span>experimental next-day workspace estimate<br>${e(f.method)} · ${f.data_source === 'synthetic_kaggle'?'Kaggle-derived synthetic demo data':'Unverified workspace data'}</span></div>` : '<p class="muted">No forecast is available yet. At least seven recent days of recorded workspace history are required.</p>';
    }).catch(error => { $('#detail-forecast').textContent = error.message; });
    const form = $('#admission-form');
    if (form) {
      const params = new URLSearchParams(location.search);
      for (const key of ['requested_bed_type','priority','oxygen_required','ventilator_required']) {
        const value = params.get(key === 'requested_bed_type' ? 'bed_type' : key), el = form.elements.namedItem(key);
        if (value && el) { if (el.type === 'checkbox') el.checked = value === 'true'; else el.value = value; }
      }
      form.elements.ventilator_required.addEventListener('change', () => { if (form.elements.ventilator_required.checked) form.elements.oxygen_required.checked = true; });
      form.addEventListener('submit', event => {
        event.preventDefault();
        submit(form, async () => {
          const f = form.elements;
          await api('/api/requests', {method:'POST',body:JSON.stringify({hospital_id:Number(id),requested_bed_type:f.requested_bed_type.value,priority:f.priority.value,oxygen_required:f.oxygen_required.checked,ventilator_required:f.ventilator_required.checked,join_waitlist:f.join_waitlist.checked,acknowledge_unverified:f.acknowledge_unverified.checked})});
          window.location.href = '/patient';
        });
      });
    }
  }

  if (page === 'patient') {
    let signature = '';
    async function refresh() {
      const data = await api('/api/requests/mine'), rows = data.requests;
      $('#patient-total').textContent = rows.length;
      $('#patient-pending').textContent = rows.filter(r => ['pending','waitlisted'].includes(r.status)).length;
      $('#patient-approved').textContent = rows.filter(r => r.status === 'approved').length;
      const next = JSON.stringify(rows); if (next === signature) return; signature = next;
      $('#patient-requests').innerHTML = rows.length ? rows.map(r => `<article class="request-card"><div class="request-card-head"><div><span class="request-id">REQUEST #${r.id}</span><h3><a href="/hospitals/${r.hospital_id}">${e(r.hospital_name)}</a></h3></div>${status(r.status)}</div><div class="request-meta"><span>${e(r.requested_bed_type.toUpperCase())} bed</span><span>${r.oxygen_required?'Oxygen required':'No oxygen requirement'}</span>${r.ventilator_required?'<span>Ventilator required</span>':''}<span>${e(r.priority)} priority (sorting aid)</span></div>${r.delivery_status==='internal_only'?'<p class="availability-source">Internal MediBed workspace only · Not sent to the hospital · No hospital admission confirmed.</p>':''}${r.bed_code?`<p class="small mt-3">${r.status==='approved'?'Workspace reservation':'Previous assignment'}: <strong>${e(r.bed_code)}</strong></p>`:''}<div class="request-card-bottom"><span>Created ${e(date(r.created_at))}</span>${['pending','waitlisted','approved'].includes(r.status)?`<button class="text-button" data-cancel="${r.id}">Cancel ${r.status==='approved'?'reservation':'request'}</button>`:`<span>${e(date(r.decided_at))}</span>`}</div></article>`).join('') : empty('Your next step starts here.', 'Browse Pune hospitals or create an internal workspace request. Call the hospital for actual care.');
    }
    poll(refresh);
    $('#patient-requests').addEventListener('click', async event => {
      const button = event.target.closest('[data-cancel]'); if (!button) return;
      if (!await confirmAction('Cancel this workspace request?', 'An eligible workspace reservation will be released. This does not cancel any arrangements made directly with a hospital.')) return;
      button.disabled = true;
      try { await api(`/api/requests/${button.dataset.cancel}/cancel`,{method:'POST',body:'{}'}); toast('Workspace request cancelled.'); await refresh(); await notifications(); }
      catch (error) { toast(error.message, true); }
      finally { button.disabled = false; }
    });
  }

  if (page === 'ambulances') {
    const form = $('#ambulance-filter'); let signature = '';
    const params = new URLSearchParams(location.search);
    for (const [key,value] of params) { const el = form.elements.namedItem(key); if (el) el.value = value; }
    async function refresh() {
      const data = await api('/api/ambulances?' + query(form));
      const next = JSON.stringify(data.ambulances); if (next === signature) return; signature = next;
      $('#ambulance-results').innerHTML = data.ambulances.length ? data.ambulances.map(ambulanceCard).join('') : empty('No published contacts match.', 'Try another hospital or area, or remove the status filter. A missing report does not mean a vehicle is unavailable.');
    }
    const updates = poll(refresh);
    form.addEventListener('submit', event => { event.preventDefault(); signature = ''; history.replaceState(null,'','?' + query(form)); updates.refresh(); });
  }

  if (page === 'predictions') {
    const form = $('#prediction-filter'), params = new URLSearchParams(location.search);
    if (params.has('hospital_id')) form.elements.hospital_id.value = params.get('hospital_id');
    async function refresh() {
      const f = await api('/api/predictions?' + query(form));
      $('#prediction-summary').innerHTML = forecastSummary(f);
      $('#model-method').textContent = f.forecast_available ? f.method : 'Insufficient recorded history';
      $('#model-explanation').textContent = f.explanation;
      $('#model-validation').textContent = f.validation_mae !== null ? `Chronological validation MAE: ${f.validation_mae} beds over ${f.validation_days} held-out recorded days. This is measured workspace-data error, not clinical accuracy.` : 'No measured validation result is available. No accuracy is claimed.';
      drawHistory('history-chart','history-fallback',f);
    }
    refresh().catch(error => { $('#prediction-summary').innerHTML = empty('Forecast unavailable.', error.message); });
    form.addEventListener('submit', event => { event.preventDefault(); submit(form, refresh); });
  }
})();
