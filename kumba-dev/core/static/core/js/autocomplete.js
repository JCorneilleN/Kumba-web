// core/static/core/js/autocomplete.js
function setupAutocomplete(inputId, suggestionsId) {
    const inp = document.getElementById(inputId);
    const list = document.getElementById(suggestionsId);
    let timeout = null;
  
    inp.addEventListener('input', () => {
      clearTimeout(timeout);
      timeout = setTimeout(async () => {
        if (!inp.value) { list.innerHTML = ''; return; }
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&q=${encodeURIComponent(inp.value)}&limit=5`
        );
        const data = await res.json();
        list.innerHTML = data.map(item =>
          `<button type="button" class="list-group-item list-group-item-action">
             ${item.display_name}
           </button>`
        ).join('');
  
        list.querySelectorAll('button').forEach(btn =>
          btn.addEventListener('click', () => {
            inp.value = btn.textContent.trim();
            list.innerHTML = '';
          })
        );
      }, 300);
    });
  
    document.addEventListener('click', e => {
      if (!inp.contains(e.target) && !list.contains(e.target)) {
        list.innerHTML = '';
      }
    });
  }
  
  document.addEventListener('DOMContentLoaded', () => {
    setupAutocomplete('origin', 'origin-suggestions');
    setupAutocomplete('destination', 'destination-suggestions');
  });
  