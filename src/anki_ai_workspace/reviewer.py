from __future__ import annotations

import json

from aqt import gui_hooks, mw

from .markdown_renderer import MARKDOWN_RENDERER_SCRIPT
from .reviewer_chat import controller
from .reviewer_protocol import parse_message

_registered = False
_ADDON_MODULE = __name__.split(".")[0]


def register() -> None:
    global _registered
    if _registered:
        return
    mw.addonManager.setWebExports(_ADDON_MODULE, r"web/.*\.js")
    gui_hooks.webview_will_set_content.append(_inject_reviewer_bridge)
    gui_hooks.card_will_show.append(_append_chat_button)
    gui_hooks.reviewer_did_show_question.append(_on_reviewer_did_show_question)
    gui_hooks.webview_did_receive_js_message.append(_handle_webview_message)
    _registered = True


def _append_chat_button(html: str, card, context: str) -> str:
    if context not in {"reviewQuestion", "reviewAnswer"}:
        return html
    return html + _button_markup(controller.bootstrap(card))


def _on_reviewer_did_show_question(card) -> None:
    """Synchronize only after Anki has installed the replacement reviewer page."""

    reviewer = getattr(mw, "reviewer", None)
    web = getattr(reviewer, "web", None)
    if web is not None:
        controller.on_card_shown(card, web)


def _inject_reviewer_bridge(web_content, context) -> None:
    if not _is_reviewer_webview(context):
        return
    package = mw.addonManager.addonFromModule(_ADDON_MODULE)
    bridge_path = f"/_addons/{package}/web/reviewer_bridge.js"
    if bridge_path not in web_content.js:
        web_content.js.append(bridge_path)


def _handle_webview_message(handled_result, message: str, context):
    handled, _result = handled_result
    payload = parse_message(message)
    if handled or payload is None or not _is_reviewer_context(context):
        return handled_result
    card = getattr(context, "card", None) or getattr(mw.reviewer, "card", None)
    if card is None:
        return handled_result
    controller.handle(card, context.web, payload)
    return True, None


def _is_reviewer_context(context) -> bool:
    return bool(context and hasattr(context, "card") and hasattr(context, "web"))


def _is_reviewer_webview(context) -> bool:
    return bool(context and hasattr(context, "web") and hasattr(context, "mw"))


def _button_markup(bootstrap: dict[str, object]) -> str:
    # This is data, not executable JavaScript. Escaping the closing tag keeps card
    # text or model replies from being able to terminate the JSON script element.
    bootstrap_json = json.dumps(bootstrap, ensure_ascii=False).replace("</", "<\\/")
    return (
        """
<div id="anki-ai-workspace-launcher" role="group" aria-label="AI"><button id="anki-ai-workspace-launcher-new" type="button" aria-label="New AI action" title="New AI action">✦</button><button id="anki-ai-workspace-launcher-restore" type="button" aria-label="Resume AI" title="Resume AI"><span class="anki-ai-workspace-restore-dot"></span><span class="anki-ai-workspace-restore-dot"></span><span class="anki-ai-workspace-restore-dot"></span><span class="anki-ai-workspace-restore-chevron">⌃</span></button></div>
<div id="anki-ai-workspace-shortcuts" role="group" aria-label="AI shortcuts" hidden></div>
<aside id="anki-ai-workspace-menu" aria-label="AI actions" hidden>
 <div id="anki-ai-workspace-menu-profile"></div><div id="anki-ai-workspace-menu-actions"></div>
</aside>
<section id="anki-ai-workspace-panel" aria-label="AI Workspace" hidden>
 <header id="anki-ai-workspace-titlebar">
  <div id="anki-ai-workspace-window-actions"><button id="anki-ai-workspace-close" type="button" title="Close all chats" aria-label="Close all chats"></button><button id="anki-ai-workspace-minimize" type="button" title="Hide AI" aria-label="Hide AI"></button></div>
  <div id="anki-ai-workspace-heading"><strong>AI Workspace</strong><button id="anki-ai-workspace-sessions" type="button" aria-label="Select conversation"></button></div>
 </header>
 <aside id="anki-ai-workspace-selector" aria-label="Conversations" hidden><div id="anki-ai-workspace-selector-items"></div></aside>
 <main id="anki-ai-workspace-turns"></main>
 <footer id="anki-ai-workspace-composer-shell">
  <textarea id="anki-ai-workspace-composer" rows="1" placeholder="Message…"></textarea>
  <div id="anki-ai-workspace-connection"><button id="anki-ai-workspace-health" type="button" aria-label="AI connection status"><span></span></button><span id="anki-ai-workspace-connection-label"></span><aside id="anki-ai-workspace-connection-popover" hidden><strong>AI connection unavailable</strong><button id="anki-ai-workspace-retry" type="button">Retry connection</button><button id="anki-ai-workspace-copy" type="button">Copy diagnostic</button></aside></div>
  <button id="anki-ai-workspace-send" type="button" aria-label="Send message" title="Send message">↑</button>
 </footer>
 <button id="anki-ai-workspace-resize" type="button" aria-label="Resize chat window"></button>
</section>
<style>
#anki-ai-workspace-launcher,#anki-ai-workspace-shortcuts,#anki-ai-workspace-shortcuts *,#anki-ai-workspace-menu,#anki-ai-workspace-menu *,#anki-ai-workspace-panel,#anki-ai-workspace-panel *{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif!important;letter-spacing:normal!important;text-transform:none!important}
#anki-ai-workspace-launcher{position:fixed;left:20px;bottom:20px;z-index:1000;display:flex;align-items:center;gap:6px;height:34px;margin:0;background:transparent!important;color:#fff!important}#anki-ai-workspace-launcher button{display:grid;place-items:center;width:34px;height:34px;margin:0;padding:0;border:0!important;border-radius:50%;background:#111!important;color:#fff!important;font-size:14px!important;font-weight:700!important;line-height:1!important;cursor:pointer;box-shadow:0 3px 10px rgba(0,0,0,.14);transition:transform .15s ease,box-shadow .15s ease,background .15s ease}#anki-ai-workspace-launcher button:hover{transform:translateY(-1px);background:#242424!important;box-shadow:0 5px 13px rgba(0,0,0,.18)}#anki-ai-workspace-launcher-restore{display:none!important}#anki-ai-workspace-launcher.anki-ai-workspace-has-hidden-workspace #anki-ai-workspace-launcher-restore{display:grid!important}#anki-ai-workspace-launcher-restore .anki-ai-workspace-restore-dot{display:none}#anki-ai-workspace-launcher-restore .anki-ai-workspace-restore-chevron{display:block;font-size:17px;line-height:1;transform:translateY(1px)}#anki-ai-workspace-launcher-restore.anki-ai-workspace-working .anki-ai-workspace-restore-chevron{display:none}#anki-ai-workspace-launcher-restore.anki-ai-workspace-working::before{content:"•••";display:block;letter-spacing:2px;font-size:13px;line-height:1;transform:translateX(1px);animation:anki-ai-workspace-restore-ellipsis 1.2s ease-in-out infinite}@keyframes anki-ai-workspace-restore-ellipsis{0%,100%{opacity:.42}50%{opacity:1}}
#anki-ai-workspace-shortcuts{position:fixed;left:64px;bottom:20px;z-index:1000;display:flex;max-width:calc(100vw - 84px);height:34px;gap:1px;margin:0;padding:2px;overflow-x:auto;overflow-y:hidden;border:1px solid rgba(255,255,255,.1);border-radius:17px;background:rgba(17,17,17,.94)!important;box-shadow:0 3px 10px rgba(0,0,0,.14);backdrop-filter:blur(12px);scrollbar-width:none}#anki-ai-workspace-shortcuts::-webkit-scrollbar{display:none}#anki-ai-workspace-shortcuts[hidden]{display:none!important}#anki-ai-workspace-shortcuts button{flex:0 0 auto;height:28px;margin:0;padding:0 10px;border:0!important;border-radius:14px;background:transparent!important;color:#fff!important;font-size:11px!important;font-weight:600!important;line-height:28px!important;white-space:nowrap;cursor:pointer;box-shadow:none!important;transition:background .15s ease,color .15s ease,opacity .15s ease}#anki-ai-workspace-shortcuts button:hover{background:rgba(255,255,255,.12)!important;color:#fff!important}#anki-ai-workspace-shortcuts button:disabled{opacity:.42;cursor:default;background:transparent!important}
#anki-ai-workspace-menu{position:fixed;left:20px;bottom:70px;z-index:1002;width:min(300px,calc(100vw - 40px));padding:8px;border:1px solid #e3e3e3;border-radius:12px;background:#fff;color:#111;box-shadow:0 12px 30px rgba(0,0,0,.16)}#anki-ai-workspace-menu[hidden],#anki-ai-workspace-panel[hidden],#anki-ai-workspace-selector[hidden],#anki-ai-workspace-connection-popover[hidden]{display:none!important}
#anki-ai-workspace-menu-profile,.anki-ai-workspace-group{padding:8px 10px 5px;color:#777;font-size:10px!important;font-weight:700!important;letter-spacing:.08em!important;text-transform:uppercase!important}#anki-ai-workspace-menu button,#anki-ai-workspace-selector button{display:flex;width:100%;min-height:38px;align-items:center;margin:0;padding:0 10px;border:0!important;border-radius:7px;background:transparent!important;color:inherit!important;font-size:13px!important;font-weight:500!important;text-align:left;cursor:pointer}#anki-ai-workspace-menu button:hover,#anki-ai-workspace-selector button:hover{background:#f2f2f2!important}.anki-ai-workspace-menu-divider{height:1px;margin:7px 4px;background:#e8e8e8}.anki-ai-workspace-empty{padding:8px 10px;color:#777;font-size:12px!important}.anki-ai-workspace-menu .anki-ai-workspace-configure{min-height:34px;color:#666!important;font-size:12px!important;font-weight:600!important}
#anki-ai-workspace-panel{--acc-bg:#fff;--acc-border:#e3e3e3;--acc-text:#111;--acc-muted:#777;position:fixed;z-index:1001;min-width:300px;min-height:320px;overflow:visible;display:flex;flex-direction:column;border:1px solid var(--acc-border);border-radius:12px;background:var(--acc-bg);color:var(--acc-text);box-shadow:0 16px 42px rgba(0,0,0,.16);font-size:14px!important}
#anki-ai-workspace-titlebar{display:flex;align-items:center;gap:15px;height:52px;padding:0 16px;border-bottom:1px solid var(--acc-border);border-radius:12px 12px 0 0;cursor:move;user-select:none}#anki-ai-workspace-heading,#anki-ai-workspace-window-actions{display:flex;align-items:center;gap:8px;min-width:0;height:100%}#anki-ai-workspace-window-actions{flex:none;gap:8px}#anki-ai-workspace-heading{flex:1}#anki-ai-workspace-heading strong{flex:none;font-size:14px!important;font-weight:700!important}#anki-ai-workspace-sessions{position:relative;width:min(420px,calc(100vw - 250px));height:34px;min-width:160px;padding:0 34px 0 12px;border:0!important;border-radius:8px;background:#f4f4f4!important;color:#111!important;font-size:13px!important;font-weight:600!important;text-align:left;text-overflow:ellipsis;white-space:nowrap;overflow:hidden;cursor:pointer}#anki-ai-workspace-sessions::after{content:"";position:absolute;right:14px;top:12px;width:7px;height:7px;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(45deg)}#anki-ai-workspace-sessions:hover{background:#ececec!important}#anki-ai-workspace-close,#anki-ai-workspace-minimize{width:14px;height:14px;margin:0;padding:0;border:0!important;border-radius:50%;font-size:0!important;line-height:1!important;cursor:pointer;box-shadow:inset 0 -1px 1px rgba(0,0,0,.18)!important}#anki-ai-workspace-close{background:#ff5f57!important}#anki-ai-workspace-minimize{background:#febc2e!important}#anki-ai-workspace-close:hover,#anki-ai-workspace-minimize:hover{filter:brightness(.93)}
#anki-ai-workspace-selector{position:absolute;z-index:10;top:44px;left:136px;width:356px;max-height:340px;overflow:auto;padding:8px;border:1px solid var(--acc-border);border-radius:10px;background:#fff;box-shadow:0 13px 30px rgba(0,0,0,.17);text-align:left}.anki-ai-workspace-group{text-align:left!important}#anki-ai-workspace-selector button{color:#111!important;text-align:left!important}#anki-ai-workspace-selector button.anki-ai-workspace-session{position:relative;padding-left:32px!important}.anki-ai-workspace-session::before{content:"";position:absolute;left:11px;top:50%;width:10px;height:10px;border-radius:50%;transform:translateY(-50%);background:#b5b5b5}.anki-ai-workspace-session-pending::before{background:#f59e0b}.anki-ai-workspace-session-active{background:#f1f1f1!important;font-weight:700!important}
#anki-ai-workspace-turns{flex:1;min-height:120px;overflow-y:auto;padding:30px 32px;display:flex;flex-direction:column;gap:26px;text-align:left}.anki-ai-workspace-turn{max-width:78%;overflow-wrap:anywhere;font-size:14px!important;line-height:1.62}.anki-ai-workspace-user{align-self:flex-end;padding:11px 14px;border-radius:18px 18px 4px 18px;background:#f1f1f1;color:#111;white-space:pre-wrap}.anki-ai-workspace-user.anki-ai-workspace-action{min-width:148px;border:1px solid #dedede;background:#fafafa;white-space:normal}.anki-ai-workspace-action-kind{display:block;margin-bottom:2px;color:#777;font-size:10px!important;font-weight:700!important;letter-spacing:.08em!important;text-transform:uppercase!important}.anki-ai-workspace-action-title{display:block;font-weight:600!important}.anki-ai-workspace-action-state{display:block;margin-top:3px;color:#777;font-size:11px!important}.anki-ai-workspace-action[data-state="failed"] .anki-ai-workspace-action-state{color:#b91c1c}.anki-ai-workspace-action[data-state="cancelled"] .anki-ai-workspace-action-state{color:#a16207}.anki-ai-workspace-assistant{align-self:stretch;max-width:none;white-space:normal}.anki-ai-workspace-assistant p{margin:0 0 1em}.anki-ai-workspace-assistant p:last-child,.anki-ai-workspace-assistant ul:last-child,.anki-ai-workspace-assistant ol:last-child{margin-bottom:0}.anki-ai-workspace-assistant h1,.anki-ai-workspace-assistant h2,.anki-ai-workspace-assistant h3{margin:0 0 .65em;font-size:1em!important}.anki-ai-workspace-assistant ul,.anki-ai-workspace-assistant ol{margin:.2em 0 1em;padding-left:1.45em}.anki-ai-workspace-assistant code{padding:.12em .32em;border-radius:4px;background:#f1f1f1}.anki-ai-workspace-typing{align-self:flex-start;display:flex;align-items:center;gap:5px;min-width:58px;padding:12px 14px;border-radius:18px 18px 18px 4px;background:#f1f1f1}.anki-ai-workspace-typing span{width:6px;height:6px;border-radius:50%;background:#777;animation:anki-ai-workspace-typing 1.2s ease-in-out infinite}.anki-ai-workspace-typing span:nth-child(2){animation-delay:.15s}.anki-ai-workspace-typing span:nth-child(3){animation-delay:.3s}@keyframes anki-ai-workspace-typing{0%,60%,100%{opacity:.32;transform:translateY(0)}30%{opacity:1;transform:translateY(-3px)}}
#anki-ai-workspace-composer-shell{position:relative;display:grid;grid-template-columns:minmax(0,1fr) 40px;grid-template-rows:1fr 22px;column-gap:8px;align-items:start;margin:12px;padding:9px 12px 7px;border:1px solid #dedede;border-radius:18px;background:#fff;min-height:84px}#anki-ai-workspace-composer{grid-column:1 / 3;grid-row:1;width:100%;min-height:36px;max-height:110px;margin:0;padding:4px 2px;border:0!important;background:transparent!important;color:#111!important;font-size:14px!important;line-height:20px!important;outline:none!important;resize:none}#anki-ai-workspace-composer::placeholder{color:#969696!important}#anki-ai-workspace-connection{grid-column:1;grid-row:2;position:relative;display:flex;align-items:center;gap:6px;align-self:end;height:20px;color:#808080;font-size:11px!important}#anki-ai-workspace-health{display:grid;place-items:center;width:18px;height:18px;margin:0;padding:0;border:0!important;background:transparent!important;cursor:default}#anki-ai-workspace-health span{display:block;width:10px;height:10px;border-radius:50%;background:#a7a7a7}#anki-ai-workspace-health[data-state="connected"] span{background:#22c55e}#anki-ai-workspace-health[data-state="unavailable"]{cursor:pointer}#anki-ai-workspace-health[data-state="unavailable"] span{background:#ef4444}#anki-ai-workspace-connection-popover{position:absolute;z-index:12;bottom:25px;left:0;width:238px;padding:10px;border:1px solid #dedede;border-radius:10px;background:#fff;box-shadow:0 12px 28px rgba(0,0,0,.16);color:#111}#anki-ai-workspace-connection-popover strong{display:block;margin:1px 2px 8px;font-size:12px!important}#anki-ai-workspace-connection-popover button{display:block;width:100%;height:30px;margin:0;padding:0 8px;border:0!important;border-radius:6px;background:transparent!important;color:#111!important;font-size:12px!important;text-align:left;cursor:pointer}#anki-ai-workspace-connection-popover button:hover{background:#f2f2f2!important}
#anki-ai-workspace-send{grid-column:2;grid-row:2;justify-self:end;align-self:end;display:grid;place-items:center;width:28px;height:28px;margin:-5px 1px 0 0;padding:0;border:0!important;border-radius:50%;background:#111!important;color:#fff!important;font-size:18px!important;font-weight:400!important;line-height:1!important;cursor:pointer}#anki-ai-workspace-send:disabled{opacity:.35;cursor:default}#anki-ai-workspace-resize{position:absolute;right:3px;bottom:3px;width:12px;height:12px;border:0!important;background:transparent!important;opacity:0;cursor:nwse-resize}
.nightMode #anki-ai-workspace-panel{--acc-bg:#111;--acc-border:#373737;--acc-text:#fff;--acc-muted:#999;box-shadow:0 16px 42px rgba(0,0,0,.42)}.nightMode #anki-ai-workspace-menu,.nightMode #anki-ai-workspace-selector,.nightMode #anki-ai-workspace-connection-popover,.nightMode #anki-ai-workspace-composer-shell{background:#111;color:#fff;border-color:#373737}.nightMode #anki-ai-workspace-launcher{color:#111!important}.nightMode #anki-ai-workspace-launcher button{background:#fff!important;color:#111!important}.nightMode #anki-ai-workspace-sessions,.nightMode .anki-ai-workspace-user{background:#242424!important;color:#fff!important}.nightMode .anki-ai-workspace-user.anki-ai-workspace-action{border-color:#454545;background:#1b1b1b!important}.nightMode .anki-ai-workspace-action-kind,.nightMode .anki-ai-workspace-action-state{color:#999}.nightMode #anki-ai-workspace-composer,.nightMode #anki-ai-workspace-selector button,.nightMode #anki-ai-workspace-connection-popover,.nightMode #anki-ai-workspace-connection-popover button{color:#fff!important}.nightMode #anki-ai-workspace-menu button:hover,.nightMode #anki-ai-workspace-selector button:hover,.nightMode #anki-ai-workspace-connection-popover button:hover,.nightMode .anki-ai-workspace-session-active{background:#272727!important}.nightMode .anki-ai-workspace-assistant code{background:#272727}.nightMode #anki-ai-workspace-resize{filter:invert(1)}
/* Reviewer card templates often use !important button/footer rules. Reassert the
   component geometry here so the workspace remains independent of those styles. */
#anki-ai-workspace-panel{display:flex!important;flex-direction:column!important;overflow:visible!important}
#anki-ai-workspace-titlebar{display:flex!important;flex:0 0 52px!important;height:52px!important;min-height:52px!important;margin:0!important}
#anki-ai-workspace-heading,#anki-ai-workspace-window-actions{display:flex!important;align-items:center!important;height:52px!important;margin:0!important;padding:0!important}
#anki-ai-workspace-sessions{display:block!important;width:min(420px,calc(100vw - 255px))!important;max-width:420px!important;min-width:160px!important;height:34px!important;min-height:34px!important;margin:0!important;box-shadow:none!important}
#anki-ai-workspace-close,#anki-ai-workspace-minimize{display:block!important;width:14px!important;height:14px!important;min-width:14px!important;min-height:14px!important;margin:0!important;padding:0!important}
#anki-ai-workspace-selector{position:absolute!important;z-index:1004!important;top:44px!important;left:136px!important;width:356px!important;min-width:356px!important;max-width:356px!important;margin:0!important;text-align:left!important}
#anki-ai-workspace-menu{display:block!important;width:292px!important;min-width:292px!important;max-width:292px!important;margin:0!important;padding:8px!important}
#anki-ai-workspace-menu button,#anki-ai-workspace-selector button{display:flex!important;width:100%!important;height:38px!important;min-height:38px!important;margin:0!important;padding:0 10px!important;box-shadow:none!important;text-shadow:none!important}
#anki-ai-workspace-menu-profile,.anki-ai-workspace-group{display:block!important;margin:0!important;padding:8px 10px 5px!important;line-height:12px!important}
#anki-ai-workspace-menu-divider{display:block!important;height:1px!important;min-height:1px!important;margin:7px 4px!important;padding:0!important}
#anki-ai-workspace-turns{display:flex!important;flex:1 1 auto!important;min-height:0!important;margin:0!important;padding:30px 32px!important}
#anki-ai-workspace-composer-shell{display:grid!important;grid-template-columns:minmax(0,1fr) 40px!important;grid-template-rows:1fr 22px!important;flex:0 0 84px!important;width:auto!important;height:84px!important;min-height:84px!important;margin:12px!important;padding:9px 12px 7px!important}
#anki-ai-workspace-composer{display:block!important;width:100%!important;height:auto!important;min-height:36px!important;margin:0!important;padding:4px 2px!important;box-shadow:none!important}
#anki-ai-workspace-connection{display:flex!important;height:20px!important;min-height:20px!important;margin:0!important;padding:0!important}
#anki-ai-workspace-health{display:grid!important;width:18px!important;height:18px!important;min-height:18px!important;margin:0!important;padding:0!important;box-shadow:none!important}
#anki-ai-workspace-send{display:grid!important;width:28px!important;height:28px!important;min-width:28px!important;min-height:28px!important;margin:-5px 1px 0 0!important;padding:0!important;box-shadow:none!important}
</style>
<script id="anki-ai-workspace-bootstrap" type="application/json">"""
        + bootstrap_json
        + """</script>
<script id="anki-ai-workspace-client" type="application/x-anki-ai-workspace">
"""
        + MARKDOWN_RENDERER_SCRIPT
        + """
(()=>{
 const send=value=>pycmd('anki-ai-workspace:'+JSON.stringify(value)),q=value=>document.querySelector(value);
 const panel=q('#anki-ai-workspace-panel'),turns=q('#anki-ai-workspace-turns'),sessions=q('#anki-ai-workspace-sessions'),selector=q('#anki-ai-workspace-selector'),items=q('#anki-ai-workspace-selector-items'),composer=q('#anki-ai-workspace-composer'),sendButton=q('#anki-ai-workspace-send'),health=q('#anki-ai-workspace-health'),healthLabel=q('#anki-ai-workspace-connection-label'),connectionPopover=q('#anki-ai-workspace-connection-popover'),titlebar=q('#anki-ai-workspace-titlebar'),resize=q('#anki-ai-workspace-resize'),shortcuts=q('#anki-ai-workspace-shortcuts');
 let layout=null,interaction=null,pending=false,renderedConversation=null,scrollSaveTimer=null;
 const number=(value,fallback)=>Number.isFinite(Number(value))?Number(value):fallback;
 const defaults=()=>({left:16,top:Math.round(innerHeight*.1),width:Math.max(360,Math.round(innerWidth/3)),height:Math.round(innerHeight*.78)});
 const clamp=value=>{const width=Math.max(1,innerWidth),height=Math.max(1,innerHeight),minWidth=Math.min(300,width),minHeight=Math.min(320,height),nextWidth=Math.min(Math.max(minWidth,number(value.width,minWidth)),width),nextHeight=Math.min(Math.max(minHeight,number(value.height,minHeight)),height);return{left:Math.min(Math.max(0,number(value.left,0)),width-nextWidth),top:Math.min(Math.max(0,number(value.top,0)),height-nextHeight),width:nextWidth,height:nextHeight}};
 const apply=value=>{layout=clamp(value);Object.assign(panel.style,{left:layout.left+'px',top:layout.top+'px',width:layout.width+'px',height:layout.height+'px'})};
 const begin=(mode,event,target)=>{interaction={mode,pointerId:event.pointerId,target,startX:event.clientX,startY:event.clientY,layout:{...layout}};target.setPointerCapture(event.pointerId);event.preventDefault()};
 const move=event=>{if(!interaction||event.pointerId!==interaction.pointerId)return;const next={...interaction.layout},dx=event.clientX-interaction.startX,dy=event.clientY-interaction.startY;if(interaction.mode==='move'){next.left+=dx;next.top+=dy}else{next.width+=dx;next.height+=dy}apply(next)};
 const end=event=>{if(!interaction||event.pointerId!==interaction.pointerId)return;const active=interaction;interaction=null;if(active.target.hasPointerCapture(event.pointerId))active.target.releasePointerCapture(event.pointerId);send({action:'save_layout',layout})};
 const button=(label,callback,className)=>{const node=document.createElement('button');node.type='button';node.textContent=label;node.className=className||'';node.onclick=callback;return node};
 const scroll=()=>({top:Math.round(turns.scrollTop),following:turns.scrollHeight-turns.scrollTop-turns.clientHeight<=4});
 const saveScroll=immediate=>{if(!renderedConversation)return;const submit=()=>send({action:'save_scroll',scroll:scroll()});if(immediate){clearTimeout(scrollSaveTimer);submit()}else{clearTimeout(scrollSaveTimer);scrollSaveTimer=setTimeout(submit,150)}};
 const group=(label,values,data)=>{if(!values.length)return;const heading=document.createElement('div');heading.className='anki-ai-workspace-group';heading.textContent=label;items.append(heading);values.forEach(session=>items.append(button(session.label,()=>{saveScroll(true);selector.hidden=true;send({action:'select_session',conversation_id:session.conversation_id,scroll:scroll()})},'anki-ai-workspace-session '+(session.pending?'anki-ai-workspace-session-pending ':'')+(session.conversation_id===data.selected_conversation_id?'anki-ai-workspace-session-active':''))))};
 const connection=(state)=>{health.dataset.state=state;const labels={connected:'Connected',checking:'Checking AI connection…',unavailable:'Unavailable'};healthLabel.textContent=labels[state];health.title=state==='connected'?'AI connected':state==='checking'?'Checking AI connection…':'AI connection unavailable';health.setAttribute('aria-label',health.title);if(state!=='unavailable')connectionPopover.hidden=true};
 const actionState=state=>({queued:'Queued',running:'Running…',cancelled:'Cancelled',failed:'Could not run'}[state]||'');
 const appendTurn=turn=>{const node=document.createElement('div'),isAction=turn.role==='user'&&turn.presentation==='action';node.className='anki-ai-workspace-turn anki-ai-workspace-'+(turn.role==='user'?'user':'assistant')+(isAction?' anki-ai-workspace-action':'');if(turn.typing){node.classList.add('anki-ai-workspace-typing');node.setAttribute('role','status');node.setAttribute('aria-label','Generating response');for(let index=0;index<3;index+=1)node.append(document.createElement('span'))}else if(turn.state)node.dataset.state=turn.state;if(!turn.typing&&turn.role==='assistant')node.innerHTML=AnkiAIWorkspaceMarkdown.render(turn.text);else if(!turn.typing&&isAction){const kind=document.createElement('span'),title=document.createElement('span'),state=document.createElement('span');kind.className='anki-ai-workspace-action-kind';kind.textContent='Action';title.className='anki-ai-workspace-action-title';title.textContent=turn.text;state.className='anki-ai-workspace-action-state';state.textContent=actionState(turn.state);node.append(kind,title);if(state.textContent)node.append(state)}else if(!turn.typing)node.textContent=turn.text;turns.append(node)};
 let hasWorkspace=false;
 const placeMenu=()=>{const menu=q('#anki-ai-workspace-menu'),trigger=q('#anki-ai-workspace-launcher-new');if(menu.hidden)return;const rect=trigger.getBoundingClientRect(),width=menu.getBoundingClientRect().width;menu.style.left=Math.max(20,Math.min(innerWidth-width-20,rect.left))+'px';menu.style.bottom=Math.max(20,innerHeight-rect.top+8)+'px'};
 const placeShortcuts=()=>{if(shortcuts.hidden)return;const rect=q('#anki-ai-workspace-launcher').getBoundingClientRect();shortcuts.style.left=Math.ceil(rect.right+10)+'px';shortcuts.style.maxWidth=Math.max(0,innerWidth-rect.right-30)+'px'};
 window.AnkiAIWorkspace={render:data=>{hasWorkspace=Boolean(data.workspace_has_sessions);const launcher=q('#anki-ai-workspace-launcher'),restore=q('#anki-ai-workspace-launcher-restore'),workspaceHidden=hasWorkspace&&!data.workspace_open;launcher.classList.toggle('anki-ai-workspace-has-hidden-workspace',workspaceHidden);restore.classList.toggle('anki-ai-workspace-working',workspaceHidden&&Boolean(data.workspace_pending));const restoreLabel=data.workspace_pending?'Resume AI · working':'Resume AI';restore.title=restoreLabel;restore.setAttribute('aria-label',restoreLabel);shortcuts.replaceChildren();data.shortcuts.forEach(action=>{const node=button(action.title,()=>send({action:'select_action',action_id:action.id}));node.disabled=Boolean(data.shortcuts_pending);shortcuts.append(node)});shortcuts.hidden=!data.shortcuts.length;requestAnimationFrame(placeShortcuts);panel.hidden=!data.open;const selected=data.sessions.find(session=>session.conversation_id===data.selected_conversation_id);sessions.textContent=selected?selected.label:'Conversations';if(!data.open)return;pending=Boolean(data.pending);if(!layout)apply(data.layout||defaults());items.replaceChildren();group('Cards',data.sessions.filter(session=>session.kind==='card'),data);group('Deck',data.sessions.filter(session=>session.kind==='deck'),data);turns.replaceChildren();data.turns.forEach(appendTurn);if(data.scroll_following){turns.scrollTop=turns.scrollHeight}else{turns.scrollTop=Math.min(data.scroll_top,Math.max(0,turns.scrollHeight-turns.clientHeight))}renderedConversation=data.selected_conversation_id;composer.disabled=!data.ready&&!pending;sendButton.disabled=!data.ready&&!pending;sendButton.textContent=pending?'■':'↑';sendButton.title=pending?'Stop generating':'Send message';sendButton.setAttribute('aria-label',sendButton.title);if(data.composer!==null&&data.composer!==undefined)composer.value=data.composer;if(data.focus_composer)composer.focus();connection(data.connection_health)}};
 q('#anki-ai-workspace-launcher-new').onclick=()=>send({action:'toggle_menu'});
 q('#anki-ai-workspace-launcher-restore').onclick=()=>send({action:'restore_workspace'});
 q('#anki-ai-workspace-close').onclick=()=>{saveScroll(true);send({action:'close_workspace',scroll:scroll()})};
 q('#anki-ai-workspace-minimize').onclick=()=>{saveScroll(true);send({action:'minimize',scroll:scroll()})};
 sessions.onclick=()=>selector.hidden=!selector.hidden;
 health.onclick=()=>{if(health.dataset.state==='unavailable')connectionPopover.hidden=!connectionPopover.hidden};
 q('#anki-ai-workspace-retry').onclick=()=>{connectionPopover.hidden=true;send({action:'retry'})};
 q('#anki-ai-workspace-copy').onclick=()=>{connectionPopover.hidden=true;send({action:'copy_diagnostic'})};
 sendButton.onclick=()=>send({action:sendButton.textContent==='■'?'cancel':'send',message:composer.value});
 titlebar.addEventListener('pointerdown',event=>{if(event.target.closest('button,textarea'))return;begin('move',event,titlebar)});
 resize.addEventListener('pointerdown',event=>{event.stopPropagation();begin('resize',event,resize)});
 [titlebar,resize].forEach(target=>{target.addEventListener('pointermove',move);target.addEventListener('pointerup',end);target.addEventListener('pointercancel',end)});
 composer.onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();const text=composer.value.trim();if(text&&!pending)send({action:'send',message:text})}};
 composer.oninput=()=>{composer.style.height='auto';composer.style.height=Math.min(composer.scrollHeight,110)+'px'};
 turns.addEventListener('scroll',()=>saveScroll(false));
 addEventListener('resize',()=>{if(layout)apply(layout);placeMenu();placeShortcuts()});
})();
(()=>{
 const send=value=>pycmd('anki-ai-workspace:'+JSON.stringify(value)),menu=document.querySelector('#anki-ai-workspace-menu'),heading=document.querySelector('#anki-ai-workspace-menu-profile'),actions=document.querySelector('#anki-ai-workspace-menu-actions'),base=window.AnkiAIWorkspace.render;
 const button=(label,callback,className)=>{const node=document.createElement('button');node.type='button';node.textContent=label;node.className=className||'';node.onclick=callback;return node};
 const placeMenu=()=>{const trigger=document.querySelector('#anki-ai-workspace-launcher-new');if(menu.hidden)return;const rect=trigger.getBoundingClientRect(),width=menu.getBoundingClientRect().width;menu.style.left=Math.max(20,Math.min(innerWidth-width-20,rect.left))+'px';menu.style.bottom=Math.max(20,innerHeight-rect.top+8)+'px'};
 window.AnkiAIWorkspace.render=data=>{menu.hidden=!data.menu_open;heading.textContent=data.menu.profile_name||'AI Workspace';actions.replaceChildren();data.menu.actions.forEach(action=>actions.append(button(action.title,()=>send({action:'select_action',action_id:action.id}))));if(!data.menu.has_profile){const empty=document.createElement('div');empty.className='anki-ai-workspace-empty';empty.textContent='No deck profile assigned.';actions.append(empty)}const divider=document.createElement('div');divider.className='anki-ai-workspace-menu-divider';actions.append(divider);actions.append(button('Custom chat',()=>send({action:'open_custom'})));actions.append(button(data.menu.deck_general_label,()=>send({action:'open_deck_general'})));const managementDivider=document.createElement('div');managementDivider.className='anki-ai-workspace-menu-divider anki-ai-workspace-management-divider';actions.append(managementDivider);actions.append(button('Configure profiles…',()=>send({action:'configure_profiles'}),'anki-ai-workspace-configure'));base(data);requestAnimationFrame(placeMenu)};
 const bootstrap=document.querySelector('#anki-ai-workspace-bootstrap');try{const initial=bootstrap&&JSON.parse(bootstrap.textContent||'null');if(initial)window.AnkiAIWorkspace.render(initial)}catch(_error){}
 send({action:'sync'});
})();
</script>
"""
    )
