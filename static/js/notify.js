// Lightweight toast notifications
// Usage: notify(type, text, {timeout: 3500, dismissible: true})
(function(){
  const CONTAINER_ID = 'notify-container';

  function ensureContainer(){
    let el = document.getElementById(CONTAINER_ID);
    if (!el) {
      el = document.createElement('div');
      el.id = CONTAINER_ID;
      el.className = 'notify-container';
      document.body.appendChild(el);
    }
    return el;
  }

  function notify(type, text, opts){
    const options = Object.assign({ timeout: 3500, dismissible: true }, opts || {});
    const container = ensureContainer();

    const item = document.createElement('div');
    item.className = 'notify ' + (type || 'info');
    item.setAttribute('role', 'status');
    item.setAttribute('aria-live', 'polite');

    const content = document.createElement('div');
    content.className = 'notify-content';
    content.textContent = String(text || '');
    item.appendChild(content);

    if (options.dismissible) {
      const close = document.createElement('button');
      close.type = 'button';
      close.className = 'notify-close';
      close.setAttribute('aria-label', 'Close');
      close.innerHTML = '&times;';
      close.addEventListener('click', () => removeItem(item));
      item.appendChild(close);
    }

    container.appendChild(item);

    // Animate in
    requestAnimationFrame(() => {
      item.classList.add('show');
    });

    let hideTimer = null;
    const startTimer = () => {
      if (options.timeout > 0) {
        hideTimer = setTimeout(() => removeItem(item), options.timeout);
      }
    };
    const clearTimer = () => { if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; } };

    // Pause on hover
    item.addEventListener('mouseenter', clearTimer);
    item.addEventListener('mouseleave', startTimer);
    startTimer();

    return item;
  }

  function removeItem(el){
    el.classList.remove('show');
    el.classList.add('hide');
    el.addEventListener('transitionend', () => {
      if (el && el.parentNode) el.parentNode.removeChild(el);
    });
  }

  // Expose
  window.notify = notify;
})();

