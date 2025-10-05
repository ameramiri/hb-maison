  // —————— دو مودال برای طرف حساب و کالا ——————
  // —————— (party-modal) ——————
  const partyModal      = document.getElementById('party-modal');
  const partyModalClose = document.getElementById('party-modal-close');
  const partyModalRows  = document.getElementById('party-modal-rows');
  const partyModalTitle = document.getElementById('party-modal-title');

  function openPartyModal(){ partyModal.style.display='block'; }
  function closePartyModal(){ partyModal.style.display='none'; }
  partyModalClose?.addEventListener('click', closePartyModal);
  partyModal?.addEventListener('click', (e)=>{ if(e.target===partyModal) closePartyModal(); });
  document.addEventListener('keydown', (e)=>{ if(e.key==='Escape') closePartyModal(); });

  function escapeHtml(s){ return (s||'').replace(/[&<>"']/g, m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }

  btnPartyModal?.addEventListener('click', ()=>{
    if (!partySelect?.value){ alert('لطفاً طرف حساب را انتخاب کنید.'); return; }
    const pid = partySelect.value;
    const pname = partySelect.options[partySelect.selectedIndex].text;
    partyModalTitle.textContent = `تراکنش‌های ${pname}`;
    partyModalRows.innerHTML = `<tr><td colspan="7" class="text-center">در حال بارگذاری...</td></tr>`;
    openPartyModal();

    fetch(`/ajax/party-txs/?party_id=${encodeURIComponent(pid)}&limit=20&source=${encodeURIComponent(window.PAGE_SOURCE || '')}`,
      {headers:{'X-Requested-With':'XMLHttpRequest'}})
      .then(r=>r.text())
      .then(html=>{ partyModalRows.innerHTML = html; })
      .catch(()=>{ partyModalRows.innerHTML = `<tr><td colspan="7">خطا در بارگذاری</td></tr>`; });
  });

  // —————— (item-modal) ——————
  const itemModal      = document.getElementById('item-modal');
  const itemModalClose = document.getElementById('item-modal-close');
  const itemModalRows  = document.getElementById('item-modal-rows');
  const itemModalTitle = document.getElementById('item-modal-title');

  function openItemModal(){ itemModal.style.display='block'; }
  function closeItemModal(){ itemModal.style.display='none'; }
  itemModalClose?.addEventListener('click', closeItemModal);
  itemModal?.addEventListener('click', (e)=>{ if(e.target===itemModal) closeItemModal(); });
  document.addEventListener('keydown', (e)=>{ if(e.key==='Escape') closeItemModal(); });

  btnItemModal?.addEventListener('click', ()=>{
    if (!itemSelect?.value){ alert('لطفاً کالا را انتخاب کنید.'); return; }
    const iid = itemSelect.value;
    const iname = itemSelect.options[itemSelect.selectedIndex].text;
    itemModalTitle.textContent = `تراکنش‌های ${iname}`;
    itemModalRows.innerHTML = `<tr><td colspan="7" class="text-center">در حال بارگذاری...</td></tr>`;
    openItemModal();

    fetch(`/ajax/item-txs/?item_id=${encodeURIComponent(iid)}&limit=20`, {headers:{'X-Requested-With':'XMLHttpRequest'}})
      .then(r=>r.text())
      .then(html=>{ itemModalRows.innerHTML = html; })
      .catch(()=>{ itemModalRows.innerHTML = `<tr><td colspan="7">خطا در بارگذاری</td></tr>`; });
  });

