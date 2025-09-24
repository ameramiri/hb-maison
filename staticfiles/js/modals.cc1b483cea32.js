document.addEventListener("DOMContentLoaded", () => {
  // === Party modal ===
  const partyModal       = document.getElementById('party-modal');
  const partyModalClose  = document.getElementById('party-modal-close');
  const partyModalScroll = document.getElementById('party-modal-scroll');
  const partyModalRows   = document.getElementById('party-modal-rows');
  const partyModalTitle  = document.getElementById('party-modal-title');

  function openPartyModal(){ 
      partyModal.style.display='block'; 
      document.body.style.overflow = "hidden";   // قفل اسکرول صفحه

      // فوکوس روی بدنهٔ مودال
      partyModalScroll.setAttribute("tabindex", "-1");
      partyModalScroll.focus();
  }

  function closePartyModal(){ 
      partyModal.style.display='none';
      const filterBox = document.getElementById("filter-from-last-settlement");
      filterBox.checked = false;
      document.body.style.overflow = "";         // آزاد کردن اسکرول
  }
  partyModalClose?.addEventListener('click', closePartyModal);
  partyModal?.addEventListener('click', (e)=>{ if(e.target===partyModal) closePartyModal(); });

  window.openPartyModalById = function(partyId, partyName){
    partyModal.setAttribute("data-current-id", partyId);
    partyModal.setAttribute("data-current-name", partyName);

    partyModalTitle.textContent = `${partyName}`;
    partyModalRows.innerHTML = `<tr><td colspan="6" class="text-center">در حال بارگذاری...</td></tr>`;

    openPartyModal();

    const url = new URL("/ajax/party-txs/", window.location.origin);
    url.searchParams.set("party_id", partyId);

    if (window.PAGE_SOURCE) {
        url.searchParams.set("source", window.PAGE_SOURCE);
    }

    const filterChecked = document.getElementById("filter-from-last-settlement")?.checked ? 1 : 0;
    url.searchParams.set("from_last", filterChecked);
  
    fetch(url, {headers:{'X-Requested-With':'XMLHttpRequest'}})
      .then(r=>r.json())
      .then(data=>{
        partyModalRows.innerHTML = data.html;

        const bal = data.balance || 0;
        const color = bal >= 0 ? "green" : "red";
        partyModalTitle.innerHTML =
          `${partyName} | <span style="color:${color}">مانده: ${bal.toLocaleString('fa-IR')} تومان</span>`;

        // اسکرول پایین
        partyModalScroll.scrollTop = partyModalScroll.scrollHeight;
      })
      .catch(()=>{ partyModalRows.innerHTML = `<tr><td colspan="6">خطا در بارگذاری</td></tr>`; });
  };

  document.getElementById("filter-from-last-settlement")
    ?.addEventListener("change", ()=>{
      const pid   = partyModal.getAttribute("data-current-id");
      const pname = partyModal.getAttribute("data-current-name");
      if(pid) window.openPartyModalById(pid, pname);
    });

  // === Item modal ===
  const itemModal       = document.getElementById('item-modal');
  const itemModalClose  = document.getElementById('item-modal-close');
  const itemModalScroll = document.getElementById('item-modal-scroll');
  const itemModalRows   = document.getElementById('item-modal-rows');
  const itemModalTitle  = document.getElementById('item-modal-title');


  function openItemModal(){ itemModal.style.display='block'; document.body.style.overflow = "hidden"; }   // قفل اسکرول صفحه
  function closeItemModal(){ 
      itemModal.style.display='none';
      document.body.style.overflow = "";         // آزاد کردن اسکرول
  }

  function openItemModal(){ 
      itemModal.style.display='block'; 
      document.body.style.overflow = "hidden";   // قفل اسکرول صفحه

      // فوکوس روی بدنهٔ مودال
      itemModalScroll.setAttribute("tabindex", "-1");
      itemModalScroll.focus();
  }
  function closeItemModal(){ itemModal.style.display='none'; }
  itemModalClose?.addEventListener('click', closeItemModal);
  itemModal?.addEventListener('click', (e)=>{ if(e.target===itemModal) closeItemModal(); });

  document.addEventListener('keydown', (e)=>{
    if(e.key === 'Escape'){ closePartyModal(); closeItemModal(); }
  });

  window.openItemModalById = function(itemId, itemName){
    itemModal.setAttribute("data-current-id", itemId);
    itemModal.setAttribute("data-current-name", itemName);

    itemModalTitle.textContent = `${itemName}`;
    itemModalRows.innerHTML = `<tr><td colspan="6" class="text-center">در حال بارگذاری...</td></tr>`;
    openItemModal();

    const url = new URL("/ajax/item-txs/", window.location.origin);
    url.searchParams.set("item_id", itemId);

    fetch(url, {headers:{'X-Requested-With':'XMLHttpRequest'}})
      .then(r=>r.json())
      .then(data=>{
      itemModalRows.innerHTML = data.html;
      itemModalScroll.scrollTop = itemModalScroll.scrollHeight;
      })
      .catch(()=>{ itemModalRows.innerHTML = `<tr><td colspan="6">خطا در بارگذاری</td></tr>`; });
  };
})