// Vue app for Research & Outreach Agent
// Depends on Vue 3 and optionally Marked (loaded via CDN in index.html)

window.renderMarkdown = (text) => {
  try { if (window.marked) return window.marked.parse(String(text||'')); } catch {}
  const esc = String(text||'').replace(/[&<>"']/g, (c)=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  return esc.replace(/\n/g,'<br/>');
};

(function(){
  const { createApp, ref, onMounted, nextTick, computed } = Vue;
  createApp({
    setup(){
      const chatId = ref(null);
      const busy = ref(false);
      const prompt = ref("");
      const messages = ref([]);
      const msgWrap = ref(null);
      const ingestText = ref("");
      const ingestId = ref("");
      const ingestTags = ref("");
      const ingestUrl = ref("");

      const lastAssistantText = computed(() => {
        for (let i = messages.value.length - 1; i >= 0; i--) {
          if (messages.value[i].role === 'bot') return messages.value[i].plain || '';
        }
        return '';
      });

      function scroll(){ nextTick(()=>{ if (msgWrap.value) msgWrap.value.scrollTop = msgWrap.value.scrollHeight; }); }
      function add(role, text){ messages.value.push({ role, html: window.renderMarkdown(text), plain: String(text) }); scroll(); }
      function updateLastAssistant(delta){
        let last = messages.value[messages.value.length-1];
        if (!last || last.role !== 'bot') { last = { role:'bot', html:'', plain:'' }; messages.value.push(last); }
        last.plain += delta;
        last.html = window.renderMarkdown(last.plain);
        scroll();
      }
      async function newChat(){
        if (busy.value) return;
        try{
          const r = await fetch('/api/new_chat'); const j = await r.json(); chatId.value = j.chat_id;
          messages.value = [];
          add('bot', 'New chat created. Ask me for a briefing or outreach draft.');
        }catch(e){ console.error(e); }
      }
      function clearChat(){ messages.value = []; }
      async function send(){
        const text = prompt.value.trim(); if (!text) return;
        add('user', text); prompt.value = '';
        if (!chatId.value) await newChat();
        busy.value = true;
        try{
          const resp = await fetch('/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ chat_id: chatId.value, message: text })});
          const reader = resp.body.getReader(); const decoder = new TextDecoder('utf-8'); let buf='';
          while(true){
            const {value, done} = await reader.read(); if (done) break;
            buf += decoder.decode(value, {stream:true});
            let i; while((i = buf.indexOf('\n\n')) >= 0){
              const block = buf.slice(0, i); buf = buf.slice(i+2);
              const ev = (block.match(/event:(.*)/)||[])[1]?.trim();
              const data = (block.match(/data:(.*)/s)||[])[1] || '';
              if (ev === 'token') updateLastAssistant(data);
            }
          }
        }catch(e){ console.error(e); }
        finally{ busy.value = false; }
      }

      async function ingest(){
        const text = ingestText.value.trim(); if (!text) return;
        try{
          const meta = {};
          if (ingestTags.value.trim()) meta.tags = ingestTags.value.split(',').map(s=>s.trim()).filter(Boolean);
          const payload = { id: ingestId.value || undefined, text, metadata: meta };
          const r = await fetch('/api/ingest', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
          const j = await r.json();
          add('bot', `Ingested to KB (id: ${j.id || 'auto'}).`);
          ingestText.value = ''; ingestId.value = ''; ingestTags.value = '';
        }catch(e){ console.error(e); }
      }

      async function ingestFromUrl(){
        const url = ingestUrl.value.trim(); if (!url) return;
        try{
          const meta = {};
          if (ingestTags.value.trim()) meta.tags = ingestTags.value.split(',').map(s=>s.trim()).filter(Boolean);
          const payload = { url, id: null, metadata: meta };
          const r = await fetch('/api/ingest_url', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
          const j = await r.json();
          if (j.ok) add('bot', `URL ingested: ${url}`); else add('bot', `URL ingest failed: ${j.detail || j.error || 'unknown error'}`);
          ingestUrl.value = '';
        }catch(e){ console.error(e); }
      }

      async function ingestFiles(ev){
        const files = ev.target.files || []; if (!files.length) return;
        try{
          for (const f of files){
            const fd = new FormData(); fd.append('file', f); fd.append('tags', ingestTags.value || '');
            const r = await fetch('/api/ingest_file', { method:'POST', body: fd });
            const j = await r.json();
            if (j.ok) add('bot', `File ingested: ${f.name}`); else add('bot', `File ingest failed: ${f.name}: ${j.detail || j.error || 'unknown error'}`);
          }
        }catch(e){ console.error(e); }
        finally { ev.target.value=''; }
      }

      async function rate(v){
        if (!chatId.value) return;
        try{
          await fetch('/api/feedback', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ chat_id: chatId.value, rating: v, comment: null, message_id: null }) });
          add('bot', v > 0 ? 'Thanks for the positive feedback!' : 'Thanks for your feedback — we will improve.');
        }catch(e){ console.error(e); }
      }
      async function copyLast(){
        try{ await navigator.clipboard.writeText(lastAssistantText.value); }catch(e){ console.error(e); }
      }

      onMounted(async ()=>{
        await newChat();
        add('bot', 'Welcome! I can research topics, build cited briefings, and draft outreach emails.');
      });

      return { chatId, busy, prompt, messages, msgWrap, ingestText, ingestId, ingestTags, ingestUrl, lastAssistantText, newChat, clearChat, send, ingest, ingestFromUrl, ingestFiles, rate, copyLast };
    }
  }).mount('#app');
})();
