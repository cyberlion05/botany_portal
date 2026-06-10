/* chat.js — shared for team chat, student chat, admin-student chat
   Reads config from window.CHAT set by the embedding template. */
(function () {
  const C = window.CHAT;
  let lastMsgId  = C.lastMsgId;
  let lastPollId = C.lastPollId;

  const chatMsgs = document.getElementById('chatMsgs');
  const msgInput = document.getElementById('msgInput');

  /* ── utilities ──────────────────────────────────────────────────── */
  function esc(t) {
    return String(t)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/\n/g, '<br>');
  }
  function scrollBottom() { chatMsgs.scrollTop = chatMsgs.scrollHeight; }
  function atBottom() {
    return chatMsgs.scrollHeight - chatMsgs.scrollTop - chatMsgs.clientHeight < 80;
  }
  scrollBottom();

  /* ── message bubble ─────────────────────────────────────────────── */
  function msgBubble(m) {
    const d = document.createElement('div');
    d.className = 'msg ' + (m.mine ? 'mine' : 'theirs');
    d.dataset.msgid = m.id;
    d.innerHTML = `<div class="msg-bubble">${esc(m.body)}</div>
      <div class="msg-meta">${esc(m.name)} · ${m.time}</div>`;
    return d;
  }

  /* ── poll card HTML ──────────────────────────────────────────────── */
  function pollInnerHTML(p) {
    const total     = p.total;
    const hasVoted  = p.my_vote !== null && p.my_vote !== undefined;
    const canVote   = !hasVoted && !p.closed;
    const closedBadge = p.closed
      ? '<span class="pill no" style="font-size:.72rem;vertical-align:middle">Closed</span>' : '';
    const closeBtn = (!p.closed && p.can_close)
      ? `<button class="btn ghost sm" onclick="closePoll(${p.id})">Close</button>` : '';

    const opts = p.options.map(o => {
      const pct = total > 0 ? Math.round(o.votes / total * 100) : 0;
      const isMyVote = hasVoted && p.my_vote === o.id;
      const showStats = hasVoted || p.closed;
      return `
        <div class="poll-option${showStats ? ' voted' : ''}"
             ${canVote ? `onclick="castVote(${p.id},${o.id})"` : ''}>
          <div class="poll-bar-fill" style="width:${pct}%"></div>
          <span class="poll-opt-text">${esc(o.text)}</span>
          ${showStats ? `<span class="poll-opt-stat">${pct}% · ${o.votes}</span>` : ''}
          ${isMyVote ? '<span class="poll-your-vote">✓ your vote</span>' : ''}
        </div>`;
    }).join('');

    return `
      <div class="poll-q-row">
        <span class="poll-question">📊 <strong>${esc(p.question)}</strong></span>
        <span style="display:flex;gap:6px;align-items:center;flex-shrink:0">
          ${closedBadge}${closeBtn}
        </span>
      </div>
      <div class="poll-opts">${opts}</div>
      <div class="poll-footer">by ${esc(p.creator)} · ${total} vote${total !== 1 ? 's' : ''}</div>`;
  }

  function buildPollCard(p) {
    const d = document.createElement('div');
    d.className = 'poll-card';
    d.id = 'poll-' + p.id;
    d.innerHTML = pollInnerHTML(p);
    return d;
  }

  function updatePollCard(p) {
    const el = document.getElementById('poll-' + p.id);
    if (el) el.innerHTML = pollInnerHTML(p);
  }

  /* ── polling loop ────────────────────────────────────────────────── */
  async function doPoll() {
    try {
      const res  = await fetch(
        `/chat/poll?room=${encodeURIComponent(C.room)}&since=${lastMsgId}&since_poll=${lastPollId}`
      );
      const data = await res.json();
      const wasBottom = atBottom();
      const empty = chatMsgs.querySelector('.chat-empty');

      data.messages.forEach(m => {
        if (!chatMsgs.querySelector(`[data-msgid="${m.id}"]`)) {
          if (empty) empty.remove();
          chatMsgs.appendChild(msgBubble(m));
        }
      });
      if (data.messages.length)
        lastMsgId = data.messages[data.messages.length - 1].id;

      data.new_polls.forEach(p => {
        if (!document.getElementById('poll-' + p.id)) {
          if (empty) empty.remove();
          chatMsgs.appendChild(buildPollCard(p));
        }
      });
      if (data.new_polls.length)
        lastPollId = data.new_polls[data.new_polls.length - 1].id;

      data.active_polls.forEach(p => updatePollCard(p));

      if (wasBottom) scrollBottom();
    } catch (_) { /* network hiccup — retry next cycle */ }
  }

  setInterval(doPoll, 3000);

  /* ── send message ────────────────────────────────────────────────── */
  window.sendMsg = async function () {
    if (!msgInput) return;
    const body = msgInput.value.trim();
    if (!body) return;
    msgInput.value = '';
    msgInput.style.height = 'auto';
    const fd = new FormData();
    fd.append('room', C.room);
    fd.append('body', body);
    fd.append('csrf_token', C.csrf);
    await fetch('/chat/send', { method: 'POST', body: fd });
    await doPoll();
  };

  /* ── vote ────────────────────────────────────────────────────────── */
  window.castVote = async function (pollId, optId) {
    const fd = new FormData();
    fd.append('option_id', optId);
    fd.append('csrf_token', C.csrf);
    const res  = await fetch(`/chat/poll/${pollId}/vote`, { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      updatePollCard(data.poll);
    } else if (data.error) {
      const el = document.getElementById('poll-' + pollId);
      if (el) {
        const err = document.createElement('p');
        err.style.cssText = 'color:var(--bloom);font-size:.8rem;margin:4px 0';
        err.textContent = data.error;
        el.appendChild(err);
        setTimeout(() => err.remove(), 3000);
      }
    }
  };

  /* ── close poll ──────────────────────────────────────────────────── */
  window.closePoll = async function (pollId) {
    if (!confirm('Close this poll? Voting will stop.')) return;
    const fd = new FormData();
    fd.append('csrf_token', C.csrf);
    await fetch(`/chat/poll/${pollId}/close`, { method: 'POST', body: fd });
    await doPoll();
  };

  /* ── poll creation form ──────────────────────────────────────────── */
  window.togglePollForm = function () {
    const f = document.getElementById('pollForm');
    if (!f) return;
    const isHidden = f.style.display === 'none' || !f.style.display;
    f.style.display = isHidden ? 'block' : 'none';
    if (isHidden) document.getElementById('pollQuestion').focus();
  };

  window.addPollOption = function () {
    const container = document.getElementById('pollOptions');
    if (!container) return;
    const count = container.querySelectorAll('.poll-opt-inp').length;
    if (count >= 6) return;
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;gap:6px;align-items:center;margin-top:6px';
    wrap.innerHTML = `
      <input class="poll-opt-inp" name="options[]" placeholder="Option ${count + 1}" required>
      <button type="button" class="btn danger sm" onclick="this.parentNode.remove()" style="flex-shrink:0">✕</button>`;
    container.appendChild(wrap);
  };

  window.submitPoll = async function () {
    const q    = (document.getElementById('pollQuestion').value || '').trim();
    const opts = [...document.querySelectorAll('#pollOptions .poll-opt-inp')]
                   .map(i => i.value.trim()).filter(Boolean);
    if (!q)           { alert('Please enter a question.'); return; }
    if (opts.length < 2) { alert('Add at least 2 options.'); return; }
    const fd = new FormData();
    fd.append('room', C.room);
    fd.append('question', q);
    fd.append('csrf_token', C.csrf);
    opts.forEach(o => fd.append('options[]', o));
    const res  = await fetch('/chat/poll/create', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.ok) {
      document.getElementById('pollQuestion').value = '';
      document.getElementById('pollOptions').innerHTML = `
        <div style="display:flex;gap:6px;margin-top:6px">
          <input class="poll-opt-inp" name="options[]" placeholder="Option 1" required style="flex:1"></div>
        <div style="display:flex;gap:6px;margin-top:6px">
          <input class="poll-opt-inp" name="options[]" placeholder="Option 2" required style="flex:1"></div>`;
      togglePollForm();
      await doPoll();
    } else {
      alert(data.error || 'Could not create poll. Try again.');
    }
  };

  /* ── keyboard shortcuts ──────────────────────────────────────────── */
  if (msgInput) {
    msgInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); }
    });
    msgInput.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 100) + 'px';
    });
  }
})();
