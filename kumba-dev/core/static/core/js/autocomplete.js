// core/static/core/js/autocomplete.js

/**
 * Sets up Nominatim-based autocomplete on a given input field.
 * @param {string} inputId - The ID of the text input.
 * @param {string} suggestionsId - The ID of the container for suggestions.
 */
function setupAutocomplete(inputId, suggestionsId) {
  const inp = document.getElementById(inputId);
  const list = document.getElementById(suggestionsId);
  let timeout = null;

  inp.addEventListener('input', () => {
    console.log(`[Autocomplete] Typing in "${inputId}":`, inp.value);
    clearTimeout(timeout);
    timeout = setTimeout(async () => {
      if (!inp.value) {
        list.innerHTML = '';
        return;
      }
      console.log(`[Autocomplete] Fetching suggestions for "${inp.value}"...`);
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&q=${encodeURIComponent(inp.value)}&limit=5`
        );
        if (!res.ok) {
          console.error(`[Autocomplete] Nominatim HTTP error:`, res.status, res.statusText);
          return;
        }
        const data = await res.json();
        console.log(`[Autocomplete] Received ${data.length} results for "${inp.value}"`, data);
        list.innerHTML = data.map(item =>
          `<button type="button" class="list-group-item list-group-item-action">
             ${item.display_name}
           </button>`
        ).join('');

        // Hook up click handlers for each suggestion
        list.querySelectorAll('button').forEach(btn =>
          btn.addEventListener('click', () => {
            console.log(`[Autocomplete] Selected "${btn.textContent.trim()}" for "${inputId}"`);
            inp.value = btn.textContent.trim();
            list.innerHTML = '';
          })
        );
      } catch (err) {
        console.error(`[Autocomplete] Fetch error:`, err);
      }
    }, 300);
  });

  // Hide suggestions when clicking outside
  document.addEventListener('click', e => {
    if (!inp.contains(e.target) && !list.contains(e.target)) {
      list.innerHTML = '';
    }
  });
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  setupAutocomplete('origin', 'origin-suggestions');
  setupAutocomplete('destination', 'destination-suggestions');
});
