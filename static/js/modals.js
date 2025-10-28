// Generic modal handler for item and party creation
function setupGenericModal(btnSelector, modalId, formSelector) {
  const btns = document.querySelectorAll(btnSelector);
  const modal = document.getElementById(modalId);
  if (!btns.length || !modal) return;
  const modalBody = modal.querySelector('.modal-body');
  const modalClose = modal.querySelector('.modal-header button');

  function initNumericFields() {
    setupNumericField('sell_price', 0);
    setupNumericField('commission_amount', 0);
    setupNumericField('commission_percent', 2);
  }

  btns.forEach(function(btn){
    btn.addEventListener('click', function(){
      const baseUrl = btn.dataset.url;                // آدرس فرم
      const tableWrapId = btn.dataset.table;      // مثلا 'items-table-wrap'
      const successMsg = btn.dataset.success;     // پیام موفقیت
      const selectId = btn.dataset.select;        // مثلا 'id_item'
      const contextType = btn.dataset.context;    // صفحه مبدا (supplier/customer)
      const url = new URL(baseUrl, window.location.origin);
      if (contextType) url.searchParams.set("context", contextType);
      
      modal.dataset.context = contextType || '';
      fetch(url)
        .then(r=>r.text())
        .then(html=>{
          modalBody.innerHTML = html;
          modal.classList.add('active');
          setTimeout(() => {
            const nameInput = modalBody.querySelector('#id_name');
            if (nameInput) nameInput.focus();
          }, 200);
          initNumericFields();   // اینجا برای بار اول

          // ذخیره تنظیمات روی modal برای استفاده موقع submit
          modal.dataset.table = tableWrapId || '';
          modal.dataset.success = successMsg || '';
          modal.dataset.select = selectId || '';
        });
    });
  });

  modalClose.addEventListener('click', ()=> modal.classList.remove('active'));
  document.addEventListener('keydown', (e)=>{ if(e.key === 'Escape'){ modal.classList.remove('active') } });
  modal.addEventListener('click', (e)=>{ if(e.target === modal){ modal.classList.remove('active') } });

  // Handle form submit
  modal.addEventListener('submit', function(e) {
    const form = e.target.closest(formSelector);
    if (!form) return;

    e.preventDefault();
    const formData = new FormData(form);

    // افزودن context از dataset
    const ctx = modal.dataset.context;
    if (ctx && !formData.has('context')) {
      formData.append('context', ctx);
    }

    fetch(form.action, {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        modal.classList.remove('active');

        // 🔄 رفرش جدول
        const tableWrapId = modal.dataset.table;
        if (tableWrapId && data.table_html) {
          const wrap = document.getElementById(tableWrapId);
          if (wrap) wrap.innerHTML = data.table_html;
        }

        // 🔄 رفرش select
        const selectId = modal.dataset.select;
        if (selectId && data.new_option) {
          const sel = document.getElementById(selectId);
          if (sel) {
            const opt = document.createElement("option");
            opt.value = data.new_option.value;
            opt.textContent = data.new_option.label;
            opt.selected = true;
            sel.appendChild(opt);
            sel.value = data.new_option.value;
            sel.dispatchEvent(new Event('change'));
          }
        }

        let msg = "عملیات با موفقیت انجام شد";
        if (modal.id === "party-create-modal") msg = "طرف حساب با موفقیت ثبت شد";
        else if (modal.id === "item-create-modal") msg = "کالا با موفقیت ثبت شد";
        notify('success', msg);
      } else {
        modalBody.innerHTML = data.form_html;
        notify('warning', 'فرم خطا دارد. موارد را اصلاح کنید.', { timeout: 5000 });
        initNumericFields();
      }
    })
    .catch(() => notify('error', 'اشکال در ارتباط با سرور'));
  });
}

document.addEventListener('DOMContentLoaded', function(){
  setupGenericModal('.btn-add-item',   'item-create-modal',  '#item-create-form');
  setupGenericModal('.btn-add-party', 'party-create-modal', '#party-create-form');
});

document.addEventListener("DOMContentLoaded", () => {
  // === Party modal ===
  const partyModal       = document.getElementById('party-modal');
  const partyModalClose  = document.getElementById('party-modal-close');
  const partyModalScroll = document.getElementById('party-modal-scroll');
  const partyModalRows   = document.getElementById('party-modal-rows');
  const partyModalTitle  = document.getElementById('party-modal-title');

  function openPartyModal(){
      partyModal.classList.add('active');
      document.body.style.overflow = "hidden";   // قفل اسکرول صفحه

      // فوکوس روی بدنهٔ مودال
      partyModalScroll.setAttribute("tabindex", "-1");
      partyModalScroll.focus();
  }

  function closePartyModal(){
      partyModal.classList.remove('active');
      const filterBox = document.getElementById("filter-from-last-settlement");
      filterBox.checked = false;
      document.body.style.overflow = "";         // آزاد کردن اسکرول
  }
  partyModalClose?.addEventListener('click', closePartyModal);
  partyModal?.addEventListener('click', (e)=>{ if(e.target===partyModal) closePartyModal(); });

  window.openPartyModalById = function(partyId, partyName){
    partyModal.setAttribute("data-current-id", partyId);
    partyModal.setAttribute("data-current-name", partyName);

    partyModalTitle.textContent = partyName;
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


  function openItemModal(){
      itemModal.classList.add('active');
      document.body.style.overflow = "hidden";   // قفل اسکرول صفحه

      // فوکوس روی بدنهٔ مودال
      itemModalScroll.setAttribute("tabindex", "-1");
      itemModalScroll.focus();
  }
  function closeItemModal(){
      itemModal.classList.remove('active');
      document.body.style.overflow = "";         // آزاد کردن اسکرول
  }

  itemModalClose?.addEventListener('click', closeItemModal);
  itemModal?.addEventListener('click', (e)=>{ if(e.target===itemModal) closeItemModal(); });

  document.addEventListener('keydown', (e)=>{
    if(e.key === 'Escape'){ closePartyModal(); closeItemModal(); }
  });

  window.openItemModalById = function(itemId, itemName){
    itemModal.setAttribute("data-current-id", itemId);
    itemModal.setAttribute("data-current-name", itemName);

    itemModalTitle.innerHTML = itemName;
    itemModalRows.innerHTML = `<tr><td colspan="6" class="text-center">در حال بارگذاری...</td></tr>`;
    openItemModal();

    const url = new URL("/ajax/item-txs/", window.location.origin);
    url.searchParams.set("item_id", itemId);

    const color = "green"
    fetch(url, {headers:{'X-Requested-With':'XMLHttpRequest'}})
      .then(r=>r.json())
      .then(data=>{
        itemModalRows.innerHTML = data.html;
        itemModalScroll.scrollTop = itemModalScroll.scrollHeight;
      })
      .catch(()=>{ itemModalRows.innerHTML = `<tr><td colspan="6">خطا در بارگذاری</td></tr>`; });
  };

  // —————— هندلینگ لینک‌ها ——————
  document.body.addEventListener('click', function(e){
    const partyLink = e.target.closest('.party-link');
    if (partyLink) {
      e.preventDefault();
      window.openPartyModalById?.(partyLink.dataset.partyId, partyLink.dataset.partyName);
    }

    const itemLink = e.target.closest('.item-link');
    if (itemLink) {
      e.preventDefault();
      window.openItemModalById?.(itemLink.dataset.itemId, itemLink.dataset.itemName);
    }
  });
})