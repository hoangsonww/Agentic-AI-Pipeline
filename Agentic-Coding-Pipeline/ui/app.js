// Lightweight helpers shared by the Vue app

window.renderMarkdown = (text) => {
  try {
    if (window.marked) {
      return window.marked.parse(String(text || ''));
    }
  } catch (e) {}
  // Fallback: escape HTML
  const esc = String(text || '').replace(/[&<>"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  return esc.replace(/\n/g, '<br/>');
};

