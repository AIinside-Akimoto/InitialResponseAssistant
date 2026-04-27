# app.py
# Streamlit クライアント（インシデント初動対応アナライザー /analyze-incident）

from __future__ import annotations

import io
import json
import mimetypes
import os
import threading
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
from streamlit_back_camera_input import back_camera_input


# =====================
# 環境変数（画面からは変更不可）
# =====================
API_BASE_URL = os.environ.get("API_BASE_URL", "").strip()
API_KEY = os.environ.get("API_KEY", "").strip()


def parse_timeout(default: int = 120) -> int:
    """環境変数 API_TIMEOUT_SEC を秒として読み取り、未指定/不正なら default を返す。"""
    raw = os.environ.get("API_TIMEOUT_SEC", "").strip()
    if not raw:
        return default

    try:
        value = int(raw)
    except ValueError:
        return default

    return value if value > 0 else default


TIMEOUT_SEC = parse_timeout(120)

st.set_page_config(page_title="初動対応アシスタント", layout="wide")


# =====================
# APIウォームアップ（初回アクセスの待ちを軽減する目的）
# =====================
def wake_up_api() -> None:
    """APIを軽く叩いてウォームアップする（失敗しても無視）。"""
    if not API_BASE_URL or not API_KEY:
        return

    headers = {"x-api-key": API_KEY, "accept": "application/json"}
    data = {"query": "ping"}

    try:
        # ベースURLのみ叩く（エンドポイントが異なる環境でも極力害が出ないように）
        requests.post(API_BASE_URL, headers=headers, data=data, timeout=5)
    except Exception:
        return


if "warmed_up" not in st.session_state:
    # 画面表示をブロックしないため別スレッドで実行
    thread = threading.Thread(target=wake_up_api, daemon=True)
    thread.start()
    st.session_state["warmed_up"] = True
    st.toast("AIエンジンを起動中...", icon="🚀")


# =====================
# 選択肢（設備）
# =====================

EQUIPMENT_OPTIONS: List[str] = [
    "洗浄装置",
    "搬送コンベア",
    "油圧プレス",
]


# =====================
# 便利関数
# =====================
def safe_dict(value: Any) -> Dict[str, Any]:
    """dict でなければ空dictを返す。"""
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> List[str]:
    """list[str] でなければ空リストを返す。"""
    return value if isinstance(value, list) else []

def log_stdout(obj: Any, prefix: str = "") -> None:
    """デバッグ用に標準出力へ出す（画面には出さない）。"""
    try:
        if isinstance(obj, (dict, list)):
            text = json.dumps(obj, ensure_ascii=False, indent=2)
        else:
            text = str(obj)
    except Exception:
        text = str(obj)

    if prefix:
        print(prefix)
    print(text, flush=True)


def render_bullets(items: Optional[List[str]]) -> None:
    """リストを箇条書きで展開表示する。"""
    if not items:
        st.info("（該当なし）")
        return

    for item in items:
        st.markdown(f"- {item}")


def call_api(final_query: str, uploaded_file) -> Dict[str, Any]:
    """AIエージェントを呼び出して結果JSONを返す。デバッグ情報は標準出力のみに出す。"""
    endpoint = f"{API_BASE_URL.rstrip('/')}/analyze-incident"

    mime = (
        getattr(uploaded_file, "type", None)
        or mimetypes.guess_type(uploaded_file.name)[0]
        or "application/octet-stream"
    )

    # Streamlit の UploadedFile は file-like なので、そのまま渡す（サーバ側の UploadFile 互換性を高める）
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    # ファイルを送る
    original_name = uploaded_file.name
    files = {"file": (original_name, uploaded_file, mime)}
    data = {"query": final_query}
    headers = {"x-api-key": API_KEY, "accept": "application/json"}

    # リクエスト情報（標準出力のみ）
    log_stdout(
        {
            "endpoint": endpoint,
            "timeout_sec": TIMEOUT_SEC,
            "file_name": uploaded_file.name,
            "file_mime": mime,
            "query_len": len(final_query),
        },
        prefix="--- REQUEST DEBUG ---",
    )

    resp = requests.post(
        endpoint,
        headers=headers,
        data=data,
        files=files,
        timeout=TIMEOUT_SEC,
    )

    log_stdout(
        {
            "http_status": resp.status_code,
            "content_type": resp.headers.get("content-type", ""),
        },
        prefix="--- RESPONSE DEBUG ---",
    )

    if not resp.ok:
        # エラー本文も標準出力のみに出す
        log_stdout(resp.text, prefix="--- ERROR BODY (stdout) ---")
        raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)

    try:
        result: Dict[str, Any] = resp.json()
    except Exception:
        log_stdout(resp.text, prefix="--- NON-JSON BODY (stdout) ---")
        raise

    # 結果JSONも標準出力のみに出す（必要なければ削除可）
    log_stdout(result, prefix="--- RESULT JSON (stdout) ---")
    return result


# =====================
# UI
# =====================
st.title("🧯 初動対応アシスタント")
st.caption("現在の事象と関連ファイルまたはカメラ写真を送信し、初動対応計画を表示します。")

if not API_BASE_URL or not API_KEY:
    st.error(
        "環境変数が不足しています。\n\n"
        "- API_BASE_URL（例: https://api.example.com）\n"
        "- API_KEY（x-api-key の値）\n"
        "- API_TIMEOUT_SEC（任意。未指定時は 120 秒）"
    )
    st.stop()

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None
if "camera_mode" not in st.session_state:
    st.session_state["camera_mode"] = "idle"
if "captured_photo" not in st.session_state:
    st.session_state["captured_photo"] = None
if "input_source" not in st.session_state:
    st.session_state["input_source"] = None

left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("📝 問い合わせ条件")

    selected_equipment = st.selectbox(
        "設備（必須）",
        options=["選択してください"] + EQUIPMENT_OPTIONS,
    )

    query_text = st.text_area(
        "現在の事象（必須）",
        height=100,
        placeholder="例：設備が停止し、エラーコードE102が表示されています。添付ログを確認してください。",
    )

    # --- ファイルアップロード ---
    def _on_file_change():
        if st.session_state.get("file_uploader") is not None:
            st.session_state["input_source"] = "file"

    file_from_uploader = st.file_uploader(
        "関連ファイル",
        type=None,
        help="ログ、スクリーンショット、設定ファイルなど。",
        key="file_uploader",
        on_change=_on_file_change,
    )

    # --- カメラ撮影 ---
    if st.session_state["camera_mode"] == "idle":
        if st.button("📷 写真を撮る", width="stretch"):
            st.session_state["camera_mode"] = "camera"
            st.rerun()
    elif st.session_state["camera_mode"] == "camera":
        # 背面カメラをデフォルトで起動（streamlit-back-camera-input）
        photo = back_camera_input(key="rear_cam")
        if photo is not None:
            st.session_state["captured_photo"] = photo.getvalue()
            st.session_state["camera_mode"] = "preview"
            st.session_state["input_source"] = "camera"
            st.rerun()
    elif st.session_state["camera_mode"] == "preview":
        st.image(
            st.session_state["captured_photo"],
            width="stretch",
        )
        if st.button("📷 撮り直す", width="stretch"):
            st.session_state["camera_mode"] = "camera"
            st.session_state["captured_photo"] = None
            st.rerun()

    # --- 後から操作した方を優先 ---
    has_file = file_from_uploader is not None
    has_photo = st.session_state["captured_photo"] is not None

    if has_file and has_photo:
        if st.session_state["input_source"] == "camera":
            uploaded_file = io.BytesIO(st.session_state["captured_photo"])
            uploaded_file.name = "camera_photo.jpg"
            uploaded_file.type = "image/jpeg"
            st.caption("→ カメラ写真が使用されます（後から操作）")
        else:
            uploaded_file = file_from_uploader
            st.caption("→ アップロードファイルが使用されます（後から操作）")
    elif has_photo:
        uploaded_file = io.BytesIO(st.session_state["captured_photo"])
        uploaded_file.name = "camera_photo.jpg"
        uploaded_file.type = "image/jpeg"
    elif has_file:
        uploaded_file = file_from_uploader
    else:
        uploaded_file = None

    run = st.button("🚀 問い合わせ実行", type="primary", width="stretch")

    if run:
        errors: List[str] = []

        if selected_equipment == "選択してください":
            errors.append("設備を選択してください。")
        if not query_text.strip():
            errors.append("現在の事象が未入力です。")
        if uploaded_file is None:
            errors.append("関連ファイルまたは写真が必要です。ファイルをアップロードするか、写真を撮影してください。")

        if errors:
            for message in errors:
                st.error(message)
        else:
            try:
                # 直前の結果をクリアしてから検索（UIの整合性を保つ）
                st.session_state["last_result"] = None

                final_query = (
                    f"問題が発生した設備は{selected_equipment}です。\n{query_text}"
                )

                with st.spinner("AIエージェント呼び出し中..."):
                    st.session_state["last_result"] = call_api(final_query, uploaded_file)

            except requests.Timeout:
                st.error(
                    "タイムアウトしました。API_TIMEOUT_SEC を延ばすか、サーバ側の状況を確認してください。"
                )
            except requests.HTTPError:
                st.error(
                    "API呼び出しでHTTPエラーが発生しました。詳細は標準出力ログを確認してください。"
                )
            except Exception as ex:
                log_stdout(str(ex), prefix="--- UNEXPECTED ERROR (stdout) ---")
                st.error("予期せぬエラーが発生しました。詳細は標準出力ログを確認してください。")

with right:
    st.subheader("📄 結果")

    result = st.session_state.get("last_result")
    if not result:
        st.info("左側で条件を入力して「問い合わせ実行」を押すと、ここに結果が表示されます。")
    else:
        # 期待するトップレベルのキーが無い場合は、スキーマ不一致（またはエラー応答）
        required_keys = {
            "priority",
            "assumed_causes",
            "initial_response_plan",
            "similar_cases_summary",
        }
        if not isinstance(result, dict) or not required_keys.issubset(result.keys()):
            st.error("応答スキーマが想定と異なります（詳細は標準出力ログを参照）。")
            st.stop()

        tabs = st.tabs(["優先度", "想定原因", "初動対応案", "類似事例", "エスカレーション", "根拠"])

        # 優先度
        with tabs[0]:
            priority = safe_dict(result.get("priority"))
            priority_level = priority.get("level", "（不明）")

            # 優先度ごとに色を切り替える（緊急=赤、重要=オレンジ、通常=青）
            if priority_level == "緊急":
                color = "red"
            elif priority_level == "重要":
                color = "orange"
            else:
                color = "blue"

            st.markdown(
                f"**優先度：** "
                f"<span style='color:{color}; font-weight:bold;'>{priority_level}</span>",
                unsafe_allow_html=True,
            )
            
            reason = priority.get("reason", "")
            if reason:
                st.write(reason)

        # 想定原因
        with tabs[1]:
            st.markdown("### 技術的要因（仮説）")
            assumed = safe_dict(result.get("assumed_causes"))
            render_bullets(safe_list(assumed.get("technical")))

            st.markdown("### 運用的要因（仮説）")
            render_bullets(safe_list(assumed.get("operational")))

        # 初動対応案
        with tabs[2]:
            plan = safe_dict(result.get("initial_response_plan"))

            forbidden = safe_list(plan.get("forbidden_actions"))
            if forbidden:
                st.markdown("### やってはいけないこと")
                render_bullets(forbidden)

            st.markdown("### 直ちに行うべき対応（〜30分以内）")
            render_bullets(safe_list(plan.get("immediate_actions")))

            st.markdown("### 暫定対応・影響抑止策")
            render_bullets(safe_list(plan.get("temporary_measures")))

            st.markdown("### 調査と並行して行うべき運用対応")
            render_bullets(safe_list(plan.get("parallel_investigations")))

        # 類似事例
        with tabs[3]:
            summary = safe_dict(result.get("similar_cases_summary"))

            if summary.get("overview"):
                st.markdown("### 概要")
                st.write(summary.get("overview"))

            if summary.get("cause_and_effect"):
                st.markdown("### 原因と有効だった対応")
                st.write(summary.get("cause_and_effect"))

            lessons = safe_list(summary.get("lessons_learned"))
            if lessons:
                st.markdown("### 今回に活かせる教訓")
                render_bullets(lessons)
    
        # エスカレーション
        with tabs[4]:
            escalation = safe_dict(result.get("escalation_point"))
            role = escalation.get("role", "")
            trigger = escalation.get("trigger", "")

            if role:
                st.markdown("### 役割")
                st.write(role)
            else:
                st.info("（役割の提示なし）")

            if trigger:
                st.markdown("### トリガー条件")
                st.write(trigger)

        # 根拠
        with tabs[5]:
            evidence_items = safe_list(result.get("evidence"))

            if not evidence_items:
                st.info("（根拠の提示なし）")
            else:
                for item in evidence_items:
                    item = safe_dict(item)
                    source = (item or {}).get("source", "")
                    detail = (item or {}).get("detail", "")

                    if detail and source:
                        st.markdown(f"- {detail}（{source}）")
                    elif detail:
                        st.markdown(f"- {detail}")
                    elif source:
                        st.markdown(f"- {source}")
