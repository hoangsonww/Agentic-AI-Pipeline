window.renderMarkdown = (text) => {
  try { if (window.marked) return window.marked.parse(String(text||'')); } catch {}
  const esc = String(text||'').replace(/[&<>"']/g, (c)=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));
  return esc.replace(/\n/g,'<br/>');
};

(function(){
  const { createApp, ref, onMounted, nextTick } = Vue;
  createApp({
    setup(){
      const sessionId = ref(null);
      const question = ref("");
      const busy = ref(false);
      const messages = ref([]);
      const sources = ref([]);
      const msgWrap = ref(null);
      const ingestUrl = ref("");
      const ingestText = ref("");
      const ingestId = ref("");
      const ingestTitle = ref("");
      const ingestTags = ref("");

      function scroll(){ nextTick(()=>{ if (msgWrap.value) msgWrap.value.scrollTop = msgWrap.value.scrollHeight; }); }
      function add(role, text){ messages.value.push({ role, html: window.renderMarkdown(text) }); scroll(); }
      function clear(){ messages.value = []; sources.value = []; }

      async function ensureSession(){
        if (sessionId.value) return;
        const r = await fetch('/api/rag/new_session'); const j = await r.json(); sessionId.value = j.session_id;
      }

      async function ask(){
        const q = question.value.trim(); if (!q) return;
        await ensureSession(); add('user', q); question.value = '';
        busy.value = true;
        try{
          const resp = await fetch('/api/rag/ask', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ session_id: sessionId.value, question: q }) });
          const reader = resp.body.getReader(); const decoder = new TextDecoder('utf-8'); let buf='';
          while(true){
            const { value, done } = await reader.read(); if (done) break;
            buf += decoder.decode(value, { stream:true });
            let i; while((i = buf.indexOf('\n\n')) >= 0){
              const block = buf.slice(0,i); buf = buf.slice(i+2);
              const ev = (block.match(/event:(.*)/)||[])[1]?.trim();
              const data = (block.match(/data:(.*)/s)||[])[1] || '';
              if (ev === 'log') add('log', data);
              else if (ev === 'answer') add('bot', data);
              else if (ev === 'sources'){ try { sources.value = JSON.parse(data || '[]'); } catch(_){} }
            }
          }
        } finally{ busy.value = false; }
      }

      async function doIngestUrl(){
        const url = ingestUrl.value.trim(); if (!url) return; busy.value = true;
        try{
          const r = await fetch('/api/rag/ingest_text', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ url, title: null, tags: parseTags(ingestTags.value) }) });
          const j = await r.json();
          if (j.ok) add('log', `URL ingested: ${url} (chunks: ${j.chunks})`); else add('log', `URL ingest failed: ${j.error || 'unknown error'}`);
          ingestUrl.value = '';
        } finally { busy.value = false; }
      }

      function parseTags(s){ return String(s||'').split(',').map(t=>t.trim()).filter(Boolean); }

      async function doIngestText(){
        const text = ingestText.value.trim(); if (!text) return; busy.value = true;
        try{
          const payload = { id: ingestId.value || null, text, title: ingestTitle.value || null, tags: parseTags(ingestTags.value) };
          const r = await fetch('/api/rag/ingest_text', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
          const j = await r.json();
          if (j.ok) add('log', `Text ingested (id: ${j.id}, chunks: ${j.chunks})`); else add('log', `Text ingest failed: ${j.error || 'unknown error'}`);
          ingestText.value = ''; ingestId.value = ''; ingestTitle.value = '';
        } finally { busy.value = false; }
      }

      async function doIngestFiles(ev){
        const files = ev.target.files || []; if (!files.length) return; busy.value = true;
        try{
          for (const f of files){
            const fd = new FormData(); fd.append('file', f); fd.append('title', ingestTitle.value || ''); fd.append('tags', ingestTags.value || '');
            const r = await fetch('/api/rag/ingest_file', { method:'POST', body: fd });
            const j = await r.json();
            if (j.ok) add('log', `File ingested: ${f.name} (chunks: ${j.chunks})`); else add('log', `File ingest failed: ${f.name}: ${j.error || 'unknown error'}`);
          }
        } finally { busy.value = false; ev.target.value = ''; }
      }

      onMounted(async ()=>{
        await ensureSession();
        add('log', 'RAG session ready. Add sources or ask a question.');
      });

      return { sessionId, question, busy, messages, sources, msgWrap, ingestUrl, ingestText, ingestId, ingestTitle, ingestTags, ask, clear, doIngestUrl, doIngestText, doIngestFiles };
    }
  }).mount('#app');
})();

