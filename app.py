"""
app.py
------
Flask server — 4 kaam karta hai:

  GET  /              → Admin dashboard (conversations dekho)
  GET  /widget        → Chat widget page (iframe mein load hoti hai)
  POST /chat          → Message process karo (Groq AI)
  GET  /embed.js      → Client apni website pe paste karta hai

RUN:
  python app.py

DEPLOY (Render):
  Start command: python app.py
  Environment variable: PORT (Render khud set karta hai)
"""

import json, uuid, os
from flask import Flask, request, jsonify, render_template_string, Response
from flask_cors import CORS

from database import Database
from agent import CustomerAgent

# ── Load config ────────────────────────────────────────────────────────────────
with open("config.json", "r") as f:
    CONFIG = json.load(f)

# ── Init ───────────────────────────────────────────────────────────────────────
app  = Flask(__name__)
CORS(app)                          # Cross-origin allow — embed ke liye zaruri
db   = Database()
ai   = CustomerAgent(CONFIG)

PORT = int(os.environ.get("PORT", 5000))


# ═══════════════════════════════════════════════════════════════════════════════
#  CHAT API
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/chat", methods=["POST"])
def chat():
    data       = request.get_json(silent=True) or {}
    user_msg   = (data.get("message") or "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())[:8]

    if not user_msg:
        return jsonify({"error": "message required"}), 400

    history = db.get_history(session_id, CONFIG.get("max_history", 8))
    result  = ai.reply(session_id, user_msg, history)

    db.save_message(session_id, "user",      user_msg,        "user",           False)
    db.save_message(session_id, "assistant", result["text"],  result["intent"], result["escalated"])

    return jsonify({
        "reply":      result["text"],
        "intent":     result["intent"],
        "escalated":  result["escalated"],
        "session_id": session_id,
    })


@app.route("/health")
def health():
    stats = db.get_total_stats()
    return jsonify({"status": "running", "business": CONFIG["business_name"], **stats})


# ═══════════════════════════════════════════════════════════════════════════════
#  CHAT WIDGET PAGE
#  Yeh page iframe mein load hoti hai client ki website pe.
# ═══════════════════════════════════════════════════════════════════════════════

WIDGET_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ name }} Support</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f8fafc;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── Header ── */
  .header {
    background: {{ color }};
    color: #fff;
    padding: 14px 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }
  .header-avatar {
    width: 36px; height: 36px;
    background: rgba(255,255,255,0.2);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
  }
  .header-info h3 { font-size: 14px; font-weight: 600; }
  .header-info p  { font-size: 11px; opacity: .8; }
  .online-dot {
    width: 8px; height: 8px;
    background: #4ade80;
    border-radius: 50%;
    margin-left: auto;
    box-shadow: 0 0 0 2px rgba(74,222,128,.3);
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%,100% { box-shadow: 0 0 0 2px rgba(74,222,128,.3); }
    50%      { box-shadow: 0 0 0 5px rgba(74,222,128,.1); }
  }

  /* ── Messages area ── */
  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    scroll-behavior: smooth;
  }

  .bubble-wrap {
    display: flex;
    align-items: flex-end;
    gap: 6px;
  }
  .bubble-wrap.user { flex-direction: row-reverse; }

  .avatar-sm {
    width: 28px; height: 28px;
    border-radius: 50%;
    background: {{ color }};
    color: #fff;
    display: flex; align-items:center; justify-content:center;
    font-size: 13px;
    flex-shrink: 0;
  }
  .bubble-wrap.user .avatar-sm { background: #64748b; }

  .bubble {
    max-width: 75%;
    padding: 10px 13px;
    border-radius: 16px;
    font-size: 13.5px;
    line-height: 1.5;
    word-break: break-word;
  }
  .bubble.agent {
    background: #fff;
    color: #1e293b;
    border-bottom-left-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,.08);
  }
  .bubble.user {
    background: {{ color }};
    color: #fff;
    border-bottom-right-radius: 4px;
  }

  /* ── Typing indicator ── */
  .typing { display: none; }
  .typing.show { display: flex; }
  .typing-dots { display:flex; gap:4px; padding: 12px 14px; }
  .typing-dots span {
    width: 7px; height: 7px;
    background: #94a3b8;
    border-radius: 50%;
    animation: bounce 1.2s infinite;
  }
  .typing-dots span:nth-child(2) { animation-delay: .2s; }
  .typing-dots span:nth-child(3) { animation-delay: .4s; }
  @keyframes bounce {
    0%,60%,100% { transform: translateY(0); }
    30%          { transform: translateY(-8px); }
  }

  /* ── Quick replies ── */
  .quick-replies {
    padding: 6px 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    flex-shrink: 0;
  }
  .qr-btn {
    background: #fff;
    border: 1.5px solid {{ color }};
    color: {{ color }};
    border-radius: 20px;
    padding: 5px 12px;
    font-size: 12px;
    cursor: pointer;
    transition: all .15s;
  }
  .qr-btn:hover { background: {{ color }}; color:#fff; }

  /* ── Input area ── */
  .input-area {
    border-top: 1px solid #e2e8f0;
    padding: 10px 12px;
    display: flex;
    gap: 8px;
    background: #fff;
    flex-shrink: 0;
  }
  .input-area input {
    flex: 1;
    border: 1.5px solid #e2e8f0;
    border-radius: 24px;
    padding: 9px 14px;
    font-size: 13.5px;
    outline: none;
    transition: border .15s;
  }
  .input-area input:focus { border-color: {{ color }}; }
  .send-btn {
    width: 38px; height: 38px;
    background: {{ color }};
    border: none;
    border-radius: 50%;
    color: #fff;
    cursor: pointer;
    display: flex; align-items:center; justify-content:center;
    flex-shrink: 0;
    font-size: 16px;
    transition: opacity .15s;
  }
  .send-btn:hover { opacity: .85; }
  .send-btn:disabled { opacity: .4; cursor:not-allowed; }

  .powered {
    text-align: center;
    font-size: 10px;
    color: #94a3b8;
    padding: 4px;
    background: #fff;
    flex-shrink: 0;
  }
</style>
</head>
<body>

<div class="header">
  <div class="header-avatar">{{ avatar }}</div>
  <div class="header-info">
    <h3>{{ agent_name }}</h3>
    <p>{{ name }} Support</p>
  </div>
  <div class="online-dot"></div>
</div>

<div class="messages" id="msgs"></div>

<div class="bubble-wrap typing" id="typing">
  <div class="avatar-sm">{{ avatar }}</div>
  <div class="bubble agent">
    <div class="typing-dots">
      <span></span><span></span><span></span>
    </div>
  </div>
</div>

<div class="quick-replies" id="qr">
  <button class="qr-btn" onclick="send('Order status check karna hai')">📦 Order Status</button>
  <button class="qr-btn" onclick="send('Refund chahiye')">💰 Refund</button>
  <button class="qr-btn" onclick="send('Table book karni hai')">🍽️ Booking</button>
  <button class="qr-btn" onclick="send('Menu aur price batao')">📋 Menu</button>
</div>

<div class="input-area">
  <input type="text" id="inp" placeholder="Apna sawaal poochein..." autocomplete="off" />
  <button class="send-btn" id="sendBtn" onclick="send()">➤</button>
</div>

<div class="powered">Powered by ABHAY AI</div>

<script>
  const SESSION_ID = Math.random().toString(36).substr(2,8);
  const API_URL    = window.location.origin + '/chat';
  const AGENT      = "{{ agent_name }}";
  const AVATAR     = "{{ avatar }}";

  // Welcome message
  window.onload = () => {
    addBubble('agent', "{{ welcome }}");
    document.getElementById('inp').addEventListener('keydown', e => {
      if (e.key === 'Enter') send();
    });
  };

  function addBubble(role, text) {
    const msgs = document.getElementById('msgs');
    const wrap = document.createElement('div');
    wrap.className = 'bubble-wrap ' + role;

    const av = document.createElement('div');
    av.className = 'avatar-sm';
    av.textContent = role === 'agent' ? AVATAR : '👤';

    const bbl = document.createElement('div');
    bbl.className = 'bubble ' + role;
    bbl.textContent = text;

    wrap.appendChild(av);
    wrap.appendChild(bbl);
    msgs.appendChild(wrap);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function showTyping(show) {
    const t = document.getElementById('typing');
    t.className = 'bubble-wrap typing' + (show ? ' show' : '');
    if (show) {
      document.getElementById('msgs').scrollTop = 99999;
    }
  }

  async function send(preset) {
    const inp = document.getElementById('inp');
    const msg = preset || inp.value.trim();
    if (!msg) return;

    // Hide quick replies after first message
    document.getElementById('qr').style.display = 'none';

    addBubble('user', msg);
    inp.value = '';
    document.getElementById('sendBtn').disabled = true;
    showTyping(true);

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, session_id: SESSION_ID })
      });
      const data = await res.json();
      showTyping(false);
      addBubble('agent', data.reply || data.error || 'Kuch error aa gayi.');
    } catch(e) {
      showTyping(false);
      addBubble('agent', 'Internet connection check karo aur dobara try karo. 🙏');
    }

    document.getElementById('sendBtn').disabled = false;
    inp.focus();
  }
</script>
</body>
</html>"""


@app.route("/widget")
def widget():
    return render_template_string(
        WIDGET_HTML,
        name       = CONFIG["business_name"],
        agent_name = CONFIG["agent_name"],
        color      = CONFIG.get("widget_color", "#2563eb"),
        welcome    = CONFIG["welcome_message"],
        avatar     = CONFIG.get("agent_avatar", "🤖"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  EMBED.JS
#  Client apni website pe yeh script paste karta hai.
#  Yeh automatically floating chat button create karta hai.
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/embed.js")
def embed_js():
    host  = request.host_url.rstrip("/")
    color = CONFIG.get("widget_color", "#2563eb")
    name  = CONFIG["business_name"]

    js = f"""
(function() {{
  if (window.__AbhayLoaded) return;
  window.__AbhayLoaded = true;

  var COLOR = "{color}";
  var HOST  = "{host}";
  var NAME  = "{name}";

  /* ── Inject CSS animations ── */
  var style = document.createElement('style');
  style.textContent = `
    @keyframes __abhay_pulse {{
      0%   {{ box-shadow: 0 0 0 0 rgba(37,99,235,.5), 0 8px 32px rgba(0,0,0,.3); }}
      70%  {{ box-shadow: 0 0 0 14px rgba(37,99,235,0), 0 8px 32px rgba(0,0,0,.3); }}
      100% {{ box-shadow: 0 0 0 0 rgba(37,99,235,0), 0 8px 32px rgba(0,0,0,.3); }}
    }}
    @keyframes __abhay_slidein {{
      from {{ opacity:0; transform: translateY(20px) scale(.95); }}
      to   {{ opacity:1; transform: translateY(0)    scale(1);   }}
    }}
    @keyframes __abhay_slideout {{
      from {{ opacity:1; transform: translateY(0)    scale(1);   }}
      to   {{ opacity:0; transform: translateY(20px) scale(.95); }}
    }}
    #__abhay_btn {{
      animation: __abhay_pulse 2.5s infinite;
    }}
    #__abhay_btn:hover {{
      transform: scale(1.08) !important;
      box-shadow: 0 12px 40px rgba(0,0,0,.35) !important;
    }}
    #__abhay_box.open {{
      animation: __abhay_slidein .25s cubic-bezier(.34,1.56,.64,1) forwards;
    }}
    #__abhay_box.closing {{
      animation: __abhay_slideout .2s ease forwards;
    }}
  `;
  document.head.appendChild(style);

  /* ── Floating button — glassmorphism pill ── */
  var btn = document.createElement('div');
  btn.id = '__abhay_btn';
  btn.innerHTML = `
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
         stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
    <span style="color:#fff;font-size:13px;font-weight:600;
                 font-family:-apple-system,sans-serif;letter-spacing:.3px;">
      Chat
    </span>
  `;
  btn.title = NAME + ' Support';
  btn.style.cssText = [
    'position:fixed',
    'bottom:28px',
    'right:28px',
    'height:52px',
    'padding:0 20px',
    'border-radius:100px',
    'background:linear-gradient(135deg,' + COLOR + ' 0%, #1d4ed8 100%)',
    'cursor:pointer',
    'display:flex',
    'align-items:center',
    'gap:8px',
    'z-index:99999',
    'transition:transform .2s ease, box-shadow .2s ease',
    'user-select:none',
    'backdrop-filter:blur(10px)',
    '-webkit-backdrop-filter:blur(10px)',
  ].join(';');

  /* ── Notification dot (unread indicator) ── */
  var dot = document.createElement('div');
  dot.style.cssText = [
    'position:absolute',
    'top:6px','right:6px',
    'width:10px','height:10px',
    'background:#f43f5e',
    'border-radius:50%',
    'border:2px solid #fff',
  ].join(';');
  btn.appendChild(dot);

  /* ── Chat box container ── */
  var box = document.createElement('div');
  box.id = '__abhay_box';
  box.style.cssText = [
    'position:fixed',
    'bottom:96px',
    'right:28px',
    'width:360px',
    'height:520px',
    'border-radius:20px',
    'overflow:hidden',
    'border:1px solid rgba(255,255,255,.15)',
    'box-shadow:0 24px 60px rgba(0,0,0,.25), 0 0 0 1px rgba(0,0,0,.05)',
    'z-index:99998',
    'display:none',
    'background:#fff',
  ].join(';');

  var iframe = document.createElement('iframe');
  iframe.src = HOST + '/widget';
  iframe.style.cssText = 'width:100%;height:100%;border:none;display:block;';
  iframe.title = NAME + ' Support';
  box.appendChild(iframe);

  /* ── Toggle logic with animation ── */
  var isOpen = false;
  btn.onclick = function() {{
    isOpen = !isOpen;
    if (isOpen) {{
      dot.style.display = 'none';
      box.style.display = 'block';
      box.className = 'open';
      btn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
             stroke="#fff" stroke-width="2.5" stroke-linecap="round">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
        <span style="color:#fff;font-size:13px;font-weight:600;
                     font-family:-apple-system,sans-serif;">Close</span>
      `;
    }} else {{
      box.className = 'closing';
      setTimeout(function(){{ box.style.display='none'; box.className=''; }}, 200);
      btn.innerHTML = `
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
             stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span style="color:#fff;font-size:13px;font-weight:600;
                     font-family:-apple-system,sans-serif;">Chat</span>
      `;
      btn.appendChild(dot);
    }}
  }};

  document.body.appendChild(box);
  document.body.appendChild(btn);

  /* ── Mobile responsive ── */
  if (window.innerWidth < 480) {{
    box.style.width  = '92vw';
    box.style.height = '72vh';
    box.style.right  = '4vw';
    box.style.bottom = '88px';
    btn.style.right  = '16px';
    btn.style.bottom = '20px';
  }}
}})();
"""
    return Response(js, mimetype="application/javascript")


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD
#  Deploy ke baad /admin pe jaao — conversations dekho
# ═══════════════════════════════════════════════════════════════════════════════

ADMIN_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin — {{ name }}</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: sans-serif; background:#f1f5f9; color:#1e293b; }
  .topbar {
    background: {{ color }};
    color:#fff; padding:14px 24px;
    display:flex; align-items:center; justify-content:space-between;
  }
  .topbar h1 { font-size:16px; font-weight:700; }
  .stats { display:flex; gap:16px; padding:20px 24px; flex-wrap:wrap; }
  .stat-card {
    background:#fff; border-radius:12px; padding:16px 20px;
    min-width:130px; text-align:center;
    box-shadow:0 1px 4px rgba(0,0,0,.08);
  }
  .stat-card .num { font-size:28px; font-weight:700; color: {{ color }}; }
  .stat-card .lbl { font-size:11px; color:#64748b; margin-top:2px; }
  .section { padding:0 24px 24px; }
  .section h2 { font-size:14px; font-weight:600; margin-bottom:10px; color:#475569; }
  table { width:100%; border-collapse:collapse; background:#fff;
          border-radius:10px; overflow:hidden;
          box-shadow:0 1px 4px rgba(0,0,0,.08); font-size:13px; }
  th { background:#f8fafc; padding:10px 14px; text-align:left;
       color:#64748b; font-weight:600; border-bottom:1px solid #e2e8f0; }
  td { padding:10px 14px; border-bottom:1px solid #f1f5f9; }
  tr:last-child td { border-bottom:none; }
  .badge {
    display:inline-block; padding:2px 8px; border-radius:12px;
    font-size:11px; font-weight:600;
  }
  .badge.esc { background:#fee2e2; color:#dc2626; }
  .badge.ok  { background:#dcfce7; color:#16a34a; }
  a { color: {{ color }}; text-decoration:none; }
  a:hover { text-decoration:underline; }
</style>
</head><body>
<div class="topbar">
  <h1>🤖 {{ name }} — Admin Panel</h1>
  <span style="font-size:12px;opacity:.8;">ABHAY AI Dashboard</span>
</div>

<div class="stats">
  <div class="stat-card">
    <div class="num">{{ stats.total_sessions }}</div>
    <div class="lbl">Total Sessions</div>
  </div>
  <div class="stat-card">
    <div class="num">{{ stats.total_messages }}</div>
    <div class="lbl">Total Messages</div>
  </div>
  <div class="stat-card">
    <div class="num">{{ stats.total_escalations }}</div>
    <div class="lbl">Escalations</div>
  </div>
</div>

<div class="section">
  <h2>Recent Conversations</h2>
  <table>
    <thead>
      <tr>
        <th>Session ID</th>
        <th>Messages</th>
        <th>Last Active</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
    {% for s in sessions %}
      <tr>
        <td><a href="/admin/session/{{ s['session_id'] }}">{{ s['session_id'] }}</a></td>
        <td>{{ s['msg_count'] }}</td>
        <td>{{ s['last_active'] }}</td>
        <td>
          {% if s['escalations'] > 0 %}
            <span class="badge esc">⚠️ Escalated</span>
          {% else %}
            <span class="badge ok">✓ Normal</span>
          {% endif %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
</body></html>"""

SESSION_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Session {{ sid }}</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:sans-serif; background:#f1f5f9; padding:20px; }
  .back { color: {{ color }}; text-decoration:none; font-size:13px; }
  h2 { margin:12px 0 16px; font-size:15px; color:#1e293b; }
  .msg { display:flex; gap:10px; margin-bottom:12px; align-items:flex-start; }
  .msg.user { flex-direction:row-reverse; }
  .av { width:30px;height:30px;border-radius:50%;
        display:flex;align-items:center;justify-content:center;
        font-size:14px;flex-shrink:0;background: {{ color }};color:#fff; }
  .msg.user .av { background:#64748b; }
  .bbl { max-width:70%; padding:10px 13px; border-radius:14px;
         font-size:13px; line-height:1.5; }
  .bbl.agent { background:#fff; color:#1e293b;
               box-shadow:0 1px 3px rgba(0,0,0,.08); }
  .bbl.user  { background: {{ color }}; color:#fff; }
  .meta { font-size:10px; color:#94a3b8; margin-top:3px; }
</style>
</head><body>
<a class="back" href="/admin">← Back</a>
<h2>Session: {{ sid }}</h2>
{% for m in messages %}
<div class="msg {{ m['role'] if m['role'] == 'user' else 'agent' }}">
  <div class="av">{{ '👤' if m['role'] == 'user' else '🤖' }}</div>
  <div>
    <div class="bbl {{ m['role'] if m['role'] == 'user' else 'agent' }}">{{ m['content'] }}</div>
    <div class="meta">{{ m['ts'] }} · {{ m['intent'] }}</div>
  </div>
</div>
{% endfor %}
</body></html>"""


@app.route("/admin")
def admin():
    sessions = [dict(s) for s in db.get_all_sessions()]
    stats    = db.get_total_stats()
    return render_template_string(
        ADMIN_HTML,
        name     = CONFIG["business_name"],
        color    = CONFIG.get("widget_color", "#2563eb"),
        sessions = sessions,
        stats    = stats,
    )


@app.route("/admin/session/<sid>")
def admin_session(sid):
    msgs = [dict(m) for m in db.get_session_messages(sid)]
    return render_template_string(
        SESSION_HTML,
        sid      = sid,
        color    = CONFIG.get("widget_color", "#2563eb"),
        messages = msgs,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  🤖 ABHAY AI — {CONFIG['business_name']}")
    print(f"  Running on http://0.0.0.0:{PORT}")
    print(f"{'='*50}")
    print(f"  Chat Widget : http://localhost:{PORT}/widget")
    print(f"  Admin Panel : http://localhost:{PORT}/admin")
    print(f"  Embed Script: http://localhost:{PORT}/embed.js")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
