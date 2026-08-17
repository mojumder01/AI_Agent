import streamlit as st
import json
import os
import traceback
from excel_handler import (
    load_excel, save_result, save_results, find_image_column,
    get_next_empty_row, get_next_empty_row_multi, row_is_done, to_excel_bytes,
)
from response_parser import extract_field

APP_VERSION = "1.6.0"
BUILT_BY = "Muntasir"

st.set_page_config(page_title="AI Product Agent", page_icon="🤖", layout="wide")

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "agent_config.json")

# ── Config helpers ────────────────────────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ── Browser agent helper ────────────────────────────────────────────────────

def get_or_start_agent():
    from browser_agent import ClaudeAgent

    agent: ClaudeAgent = st.session_state.get("agent")
    if agent is None or not agent.is_alive():
        agent = ClaudeAgent()
        agent.start()
        st.session_state["agent"] = agent
    return agent

# ── Session state init ────────────────────────────────────────────────────────

def init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

init_state("agent", None)
init_state("config", load_config())

cfg = st.session_state.config

# ── UI ────────────────────────────────────────────────────────────────────────

st.title("🤖 AI Product Agent")
st.caption("Claude chat-এ একটা একটা করে প্রোডাক্ট প্রসেস করে Excel-এ সেভ করুন")
st.caption(f"v{APP_VERSION} · Built by {BUILT_BY}")

tab1, tab2, tab3 = st.tabs([
    "✍️  Highlights & Description",
    "⚖️  Weight",
    "🖼️  Image Check",
])

MENUS = [
    {
        "key": "highlights_desc",
        "tab": tab1,
        # একাধিক আউটপুট কলাম — Claude-এর উত্তর থেকে প্রতিটা label আলাদা কলামে সেভ হয়
        "fields": [("Highlights", "AI_Highlights"), ("Description", "AI_Description")],
    },
    {"key": "weight",          "tab": tab2, "out_col_default": "AI_Weight"},
    {"key": "image_check",     "tab": tab3, "out_col_default": "AI_Image_Check"},
]


def render_menu(menu: dict):
    key = menu["key"]
    fields = menu.get("fields")  # multi-column mode হলে [(label, out_col_default), ...]

    with menu["tab"]:

        # ── Settings row ──────────────────────────────────────────────────────
        c1, c2 = st.columns([3, 1])
        with c1:
            url = st.text_input(
                "Claude Conversation URL",
                value=cfg.get(f"url_{key}", ""),
                placeholder="https://claude.ai/chat/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                key=f"url_input_{key}",
                help="যে conversation-এ prompt আগে থেকে সেট করা আছে তার URL",
            )
            if url != cfg.get(f"url_{key}", ""):
                cfg[f"url_{key}"] = url
                save_config(cfg)

        if fields:
            out_cols = []
            with c2:
                for label, default_col in fields:
                    col = st.text_input(
                        f"{label} Column",
                        value=cfg.get(f"out_col_{key}_{label}", default_col),
                        key=f"out_col_input_{key}_{label}",
                    )
                    if col != cfg.get(f"out_col_{key}_{label}", ""):
                        cfg[f"out_col_{key}_{label}"] = col
                        save_config(cfg)
                    out_cols.append((label, col))
        else:
            with c2:
                out_col = st.text_input(
                    "Output Column",
                    value=cfg.get(f"out_col_{key}", menu["out_col_default"]),
                    key=f"out_col_input_{key}",
                )
                if out_col != cfg.get(f"out_col_{key}", ""):
                    cfg[f"out_col_{key}"] = out_col
                    save_config(cfg)

        out_col_list = [col for _, col in out_cols] if fields else [out_col]

        st.divider()

        # ── Excel upload ──────────────────────────────────────────────────────
        uploaded = st.file_uploader(
            "Excel ফাইল আপলোড করুন (.xlsx)",
            type=["xlsx", "xls"],
            key=f"upload_{key}",
        )

        upload_id = getattr(uploaded, "file_id", None) or (f"{uploaded.name}-{uploaded.size}" if uploaded else None)
        if uploaded and st.session_state.get(f"upload_id_{key}") != upload_id:
            st.session_state[f"upload_id_{key}"] = upload_id
            save_path = os.path.join(os.path.dirname(__file__), f"working_{key}.xlsx")
            with open(save_path, "wb") as f:
                f.write(uploaded.getvalue())
            st.session_state[f"df_{key}"] = load_excel(save_path)
            st.session_state[f"path_{key}"] = save_path
            # নতুন ফাইলের কলাম অনুযায়ী সিলেকশন রিসেট
            st.session_state[f"sel_cols_{key}"] = list(st.session_state[f"df_{key}"].columns)
            # অটো: প্রথম খালি রোতে যাওয়া
            auto_row = get_next_empty_row_multi(st.session_state[f"df_{key}"], out_col_list)
            st.session_state[f"row_{key}"] = auto_row if auto_row is not None else 0

        # df না থাকলে বন্ধ
        if f"df_{key}" not in st.session_state:
            st.info("Excel ফাইল আপলোড করুন।")
            return

        df = st.session_state[f"df_{key}"]
        init_state(f"row_{key}", 0)
        init_state(f"response_{key}", "")

        total = len(df)
        if total == 0:
            st.warning("এই Excel ফাইলে কোনো ডেটা রো নেই।")
            return
        cur = st.session_state[f"row_{key}"]

        # ── Row navigation ────────────────────────────────────────────────────
        nav1, nav2, nav3 = st.columns([1, 1, 4])
        with nav1:
            if st.button("◀ আগের", key=f"prev_{key}", disabled=cur == 0):
                st.session_state[f"row_{key}"] -= 1
                st.session_state[f"response_{key}"] = ""
                st.rerun()
        with nav2:
            if st.button("পরের ▶", key=f"next_{key}", disabled=cur >= total - 1):
                st.session_state[f"row_{key}"] += 1
                st.session_state[f"response_{key}"] = ""
                st.rerun()
        with nav3:
            jump = st.number_input(
                "রো নম্বরে যান (1 থেকে শুরু)",
                min_value=1, max_value=total, value=cur + 1,
                step=1, key=f"jump_{key}",
            )
            if jump - 1 != cur:
                st.session_state[f"row_{key}"] = jump - 1
                st.session_state[f"response_{key}"] = ""
                st.rerun()

        row_data = df.iloc[cur].to_dict()

        # ── Column selector ───────────────────────────────────────────────────
        all_cols = list(df.columns)
        init_state(f"sel_cols_{key}", all_cols)

        selected_cols = st.multiselect(
            "Claude-এ কোন কলামগুলো পাঠাবেন?",
            options=all_cols,
            default=st.session_state[f"sel_cols_{key}"],
            key=f"cols_{key}",
        )
        st.session_state[f"sel_cols_{key}"] = selected_cols

        # ── Message preview ───────────────────────────────────────────────────
        def build_message(row: dict):
            """দেওয়া রো থেকে Claude-এ পাঠানোর মেসেজ ও (image_check হলে) ছবির path বানায়।
            এক রো-এর preview এবং Full Auto — দুই জায়গায়ই ব্যবহার হয়।"""
            lines = [f"{c}: {row.get(c, '')}" for c in selected_cols if str(row.get(c, "")).strip()]
            text = "\n".join(lines)
            img = None
            if key == "image_check":
                img_col = find_image_column(df)
                if img_col:
                    img = str(row.get(img_col, "")).strip() or None
            return text, img

        message_text, img_path = build_message(row_data)

        if key == "image_check" and img_path:
            st.info(f"🖼️ Image path: `{img_path}`")
            if not os.path.exists(img_path):
                st.warning("⚠️ ছবির ফাইল পাওয়া যায়নি। Path ঠিক আছে কিনা দেখুন।")

        with st.expander(f"📋 রো {cur + 1}/{total} — Claude-এ যা পাঠানো হবে", expanded=True):
            st.code(message_text, language=None)

        # Already saved value
        if fields:
            saved_bits = [
                f"{label}: {str(row_data.get(col, '')).strip()[:80]}"
                for label, col in out_cols
                if str(row_data.get(col, "")).strip() not in ("", "nan")
            ]
            if saved_bits:
                st.success("✅ আগে সেভ করা আছে — " + " | ".join(saved_bits))
        else:
            existing = str(row_data.get(out_col, "")).strip()
            if existing and existing != "nan":
                st.success(f"✅ আগে সেভ করা আছে: {existing[:120]}")

        # ── Action buttons ────────────────────────────────────────────────────
        st.divider()
        b1, b2, b3, b4 = st.columns([2, 1, 1, 2])

        with b1:
            send_disabled = not url or not message_text.strip()
            if st.button("🚀 Claude-এ পাঠাও", key=f"send_{key}", type="primary", disabled=send_disabled):
                if not url:
                    st.error("Conversation URL দিন।")
                else:
                    with st.spinner("ব্রাউজার খুলছে এবং Claude-এ পাঠাচ্ছে..."):
                        try:
                            agent = get_or_start_agent()
                            agent.go_to_conversation(url)
                            response = agent.send_message(
                                message_text,
                                image_path=img_path if key == "image_check" else None,
                            )
                            st.session_state[f"response_{key}"] = response
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {type(e).__name__}: {e}")
                            st.code(traceback.format_exc())

        with b4:
            pending_rows = [i for i in range(total) if not row_is_done(df.iloc[i].to_dict(), out_col_list)]
            auto_disabled = not url or not pending_rows
            if st.button(
                f"⚡ Full Auto ({len(pending_rows)} বাকি)",
                key=f"auto_{key}",
                disabled=auto_disabled,
                help="সব বাকি রো একের পর এক, নিজে নিজে Claude-এ পাঠিয়ে সেভ করবে — এডিট করার সুযোগ থাকবে না।",
            ):
                path = st.session_state[f"path_{key}"]
                local_df = df
                progress_bar = st.progress(0.0)
                status = st.empty()
                failed = []
                succeeded = 0
                consecutive_failures = 0
                stopped_early = False

                try:
                    agent = get_or_start_agent()
                    agent.go_to_conversation(url)

                    for done_count, row_idx in enumerate(pending_rows, start=1):
                        row = local_df.iloc[row_idx].to_dict()
                        msg, img = build_message(row)
                        status.info(f"রো {row_idx + 1}/{total} পাঠানো হচ্ছে... ({done_count}/{len(pending_rows)})")

                        row_ok = False
                        if not msg.strip():
                            failed.append((row_idx + 1, "পাঠানোর মতো কোনো ডেটা নেই"))
                        else:
                            try:
                                response = agent.send_message(
                                    msg, image_path=img if key == "image_check" else None
                                )
                                if fields:
                                    parsed = {label: extract_field(response, label) for label, _ in fields}
                                    if any(v.strip() for v in parsed.values()):
                                        values = {col: parsed.get(label, "") for label, col in out_cols}
                                        local_df = save_results(local_df, row_idx, values, path)
                                        row_ok = True
                                    else:
                                        # লেবেল খুঁজে পাওয়া যায়নি (হয়তো Claude refuse করেছে বা
                                        # অন্য কিছু বলেছে) — Full Auto-তে না সেভ করে failure হিসেবে
                                        # দেখানো হচ্ছে, যাতে ভুল ডেটা সাইলেন্টলি সেভ না হয় এবং একই
                                        # রো বারবার resend হয়ে Claude-কে duplicate spam-এর মতো না লাগে।
                                        snippet = response.strip().replace("\n", " ")[:150]
                                        failed.append((row_idx + 1, f"লেবেল পাওয়া যায়নি — Claude বলেছে: {snippet}"))
                                else:
                                    local_df = save_result(local_df, row_idx, out_col, response, path)
                                    row_ok = True
                            except Exception as e:
                                failed.append((row_idx + 1, f"{type(e).__name__}: {e}"))

                        if row_ok:
                            succeeded += 1
                            consecutive_failures = 0
                        else:
                            consecutive_failures += 1
                        progress_bar.progress(done_count / len(pending_rows))

                        if consecutive_failures >= 3:
                            stopped_early = True
                            break
                except Exception as e:
                    st.error(f"Error: {type(e).__name__}: {e}")
                    st.code(traceback.format_exc())
                finally:
                    status.empty()
                    st.session_state[f"df_{key}"] = local_df
                    next_row = get_next_empty_row_multi(local_df, out_col_list)
                    st.session_state[f"row_{key}"] = next_row if next_row is not None else total - 1
                    st.session_state[f"response_{key}"] = ""

                if stopped_early:
                    st.error(
                        f"⛔ পরপর ৩টা রো ব্যর্থ হওয়ায় Full Auto থামানো হয়েছে (সম্ভবত browser/composer/সেশনে "
                        f"সমস্যা, বা Claude একই কনভারসেশনে বারবার একই কনটেন্ট দেখে সন্দেহজনক মনে করছে)। "
                        f"{succeeded}/{len(pending_rows)} রো সম্পন্ন হয়েছে।\n"
                        "সমাধান: 'Browser বন্ধ করুন' চেপে ব্রাউজার রিস্টার্ট করুন, অথবা claude.ai-এ নতুন একটা "
                        "conversation বানিয়ে সেই URL বসিয়ে আবার চেষ্টা করুন।\n\n"
                        + "\n".join(f"রো {r}: {msg}" for r, msg in failed)
                    )
                elif failed:
                    st.warning(
                        f"✅ {succeeded}/{len(pending_rows)} রো সম্পন্ন। ব্যর্থ:\n"
                        + "\n".join(f"রো {r}: {msg}" for r, msg in failed)
                    )
                else:
                    st.success(f"✅ সব {len(pending_rows)} বাকি রো সম্পন্ন হয়েছে!")
                st.rerun()

        response_text = st.session_state.get(f"response_{key}", "")

        if response_text:
            st.subheader("Claude-এর উত্তর")

            if fields:
                st.caption("প্রতিটা ফিল্ড আলাদা কলামে সেভ হবে। উত্তর থেকে অটো আলাদা করা হয়েছে — দরকার হলে এডিট করুন।")
                parsed = {label: extract_field(response_text, label) for label, _ in fields}
                if not any(v.strip() for v in parsed.values()):
                    # লেবেল অনুযায়ী আলাদা করা যায়নি — পুরো উত্তর প্রথম ফিল্ডে দেখানো হচ্ছে
                    parsed[fields[0][0]] = response_text

                edited_values = {}
                for label, out_col_f in fields:
                    edited_values[out_col_f] = st.text_area(
                        label,
                        value=parsed.get(label, ""),
                        height=150,
                        key=f"edit_{key}_{label}",
                    )

                with st.expander("🔍 Claude-এর আসল উত্তর (raw)"):
                    st.code(response_text, language=None)

                with b2:
                    if st.button("💾 সেভ ও পরের রো", key=f"save_{key}", type="primary"):
                        path = st.session_state[f"path_{key}"]
                        updated_df = save_results(df, cur, edited_values, path)
                        st.session_state[f"df_{key}"] = updated_df
                        st.session_state[f"response_{key}"] = ""
                        if cur < total - 1:
                            st.session_state[f"row_{key}"] += 1
                        st.success("✅ সেভ হয়েছে!")
                        st.rerun()
            else:
                edited = st.text_area(
                    "উত্তর (দরকার হলে এডিট করুন, তারপর সেভ করুন)",
                    value=response_text,
                    height=220,
                    key=f"edit_{key}",
                )

                with b2:
                    if st.button("💾 সেভ ও পরের রো", key=f"save_{key}", type="primary"):
                        path = st.session_state[f"path_{key}"]
                        updated_df = save_result(df, cur, out_col, edited, path)
                        st.session_state[f"df_{key}"] = updated_df
                        st.session_state[f"response_{key}"] = ""
                        if cur < total - 1:
                            st.session_state[f"row_{key}"] += 1
                        st.success("✅ সেভ হয়েছে!")
                        st.rerun()

        with b3:
            if st.button("⏭️ Skip", key=f"skip_{key}"):
                st.session_state[f"response_{key}"] = ""
                if cur < total - 1:
                    st.session_state[f"row_{key}"] += 1
                st.rerun()

        # ── Progress ──────────────────────────────────────────────────────────
        st.divider()
        if any(c in df.columns for c in out_col_list):
            done = sum(row_is_done(df.iloc[i].to_dict(), out_col_list) for i in range(total))
            st.progress(done / total, text=f"সম্পন্ন: {done}/{total} রো")

        # ── Download ──────────────────────────────────────────────────────────
        st.download_button(
            "⬇️ Excel ডাউনলোড করুন (বর্তমান অবস্থা)",
            data=to_excel_bytes(df),
            file_name=f"output_{key}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_{key}",
        )


for menu in MENUS:
    render_menu(menu)

# ── Browser / Session ──────────────────────────────────────────────────────
st.sidebar.header("⚙️ Browser")

if st.sidebar.button("🔑 Claude-এ লগইন করুন / সেভ করুন"):
    with st.sidebar.status("ব্রাউজার খুলছে..."):
        try:
            agent = get_or_start_agent()
            agent.open_login()
        except Exception as e:
            st.sidebar.error(f"Error: {type(e).__name__}: {e}")
            st.sidebar.code(traceback.format_exc())
    st.sidebar.info(
        "খোলা ব্রাউজার উইন্ডোতে গিয়ে claude.ai-এ লগইন করুন। "
        "একবার লগইন করলে সেশন সেভ থাকবে — বারবার লগইন করা লাগবে না। "
        "লগইন শেষ হলে ব্রাউজার বন্ধ করার দরকার নেই।"
    )

if st.sidebar.button("🔴 Browser বন্ধ করুন"):
    agent = st.session_state.get("agent")
    if agent:
        agent.close()
        st.session_state["agent"] = None
    st.sidebar.success("Browser বন্ধ হয়েছে।")

st.sidebar.caption(f"Session ফোল্ডার: `{os.path.expanduser('~/.claude_agent_browser_profile')}`")
st.sidebar.divider()
st.sidebar.caption(f"AI Product Agent v{APP_VERSION}")
st.sidebar.caption(f"Built by {BUILT_BY}")
