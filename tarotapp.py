import os
import json
import re
import pandas as pd
import PIL.Image
import streamlit as st
from io import BytesIO
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# --- PDF生成用のライブラリ ---
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
from reportlab.lib.units import mm

# ==========================================
# 1. 初期設定とスキーマ定義
# ==========================================
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

st.set_page_config(page_title="Nabi AI Tarot Reader", layout="centered")

# --- プレミアムデザイン・フル適用 CSS ---
custom_css = """
<style>
/* 1. カラーリング ＆ 2. 余白 */
.stApp {
    background-color: #FAFCFC;
    color: #2C3E50;
}

/* 3. タイポグラフィ */
h1, h2, h3, p, .mincho {
    font-family: "Hiragino Mincho ProN", "Yu Mincho", serif !important;
    letter-spacing: 0.05em; 
}

/* 4. ディテール：重厚かつ繊細なタイトルバナー */
.premium-title-banner {
    background: linear-gradient(135deg, #1A2525, #133B3A);
    padding: 50px 20px;
    text-align: center;
    margin-bottom: 50px;
    margin-top: 10px;
    border-radius: 2px;
    box-shadow: 0 15px 40px rgba(0,0,0,0.06);
    border: 1px solid #2C3E50;
}
.premium-title-banner h1 {
    color: #FFFFFF !important;
    font-size: 2.4rem !important;
    letter-spacing: 0.1em !important;
    padding: 0 !important;
    margin: 0 0 12px 0 !important;
    font-weight: 300 !important;
}
.premium-title-banner p {
    color: #C5A059 !important;
    font-size: 1.1rem !important;
    letter-spacing: 0.15em !important;
    margin: 0 !important;
}

/* ディテール：ベタ塗りを廃止し、ミニマルな下線の見出しへ */
h3 {
    background-color: transparent !important;
    color: #133B3A !important;
    padding: 0 0 12px 0 !important;
    text-align: center;
    font-size: 1.5rem !important;
    margin-top: 50px !important;
    margin-bottom: 40px !important;
    box-shadow: none !important;
    border-bottom: 1px solid #C5A059 !important;
    font-weight: 400 !important;
}

/* 余白とディテール：ファイルアップローダーの洗練 */
[data-testid="stFileUploader"] label p {
    color: #133B3A !important;
    font-weight: 400 !important;
    font-size: 1.1rem !important;
    letter-spacing: 0.05em;
}
[data-testid="stFileUploadDropzone"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E0EBEB !important;
    border-radius: 2px !important;
    padding: 40px 20px !important;
    box-shadow: 0 5px 20px rgba(0,0,0,0.02) !important;
}
[data-testid="stFileUploadDropzone"] * {
    color: #7F8C8D !important;
}
[data-testid="stFileUploadDropzone"] button {
    background-color: #133B3A !important;
    border: none !important;
    border-radius: 2px !important;
    letter-spacing: 0.1em;
    padding: 5px 20px !important;
}
[data-testid="stFileUploadDropzone"] button * {
    color: #FFFFFF !important;
}
[data-testid="stFileUploadDropzone"] button:hover {
    background-color: #C5A059 !important;
}

/* プライマリボタンのモダン化 */
div.stButton > button[kind="primary"] {
    background-color: #133B3A !important;
    color: white !important;
    border: none !important;
    border-radius: 2px !important;
    padding: 10px 30px !important;
    font-weight: 400 !important;
    letter-spacing: 0.1em;
    transition: all 0.4s ease;
    box-shadow: 0 4px 15px rgba(0,0,0,0.08) !important;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #1A2525 !important;
    box-shadow: 0 8px 25px rgba(197, 160, 89, 0.25) !important;
    color: #C5A059 !important;
}

/* サイドバーの調整 */
[data-testid="stSidebar"] {
    background-color: #1A2525 !important;
}
[data-testid="stSidebar"] * {
    color: #FAFCFC !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #C5A059 !important;
    border-bottom: 1px solid #2C3E50 !important;
    text-align: left;
    margin-top: 20px !important;
    padding-bottom: 10px !important;
}
[data-testid="stSidebar"] hr {
    border-color: #2C3E50;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

class CardAnalysis(BaseModel):
    name: str = Field(description="カードの英語名")
    number: str = Field(description="カードの数字")
    orientation: str = Field(description="正位置 または 逆位置")

class TarotReading(BaseModel):
    pos_1: CardAnalysis
    pos_2: CardAnalysis
    pos_3: CardAnalysis
    pos_4: CardAnalysis
    pos_5: CardAnalysis
    pos_6: CardAnalysis
    pos_7: CardAnalysis
    pos_8: CardAnalysis
    pos_9: CardAnalysis
    pos_10: CardAnalysis

# ==========================================
# 2. 関数群
# ==========================================
def analyze_image(img):
    client = genai.Client(api_key=API_KEY)
    initial_file = "initial_prompt.txt"
    current_file = "current_prompt.txt"
    try:
        with open(initial_file, "r", encoding="utf-8") as f:
            initial_prompt = f.read()
    except FileNotFoundError:
        st.error(f"ファイル {initial_file} が見つかりません。先に設定を実行してください。")
        st.stop()
    current_prompt = ""
    if os.path.exists(current_file):
        with open(current_file, "r", encoding="utf-8") as f:
            current_prompt = f.read()
    final_prompt = f"{initial_prompt}\n【過去の分析から得られた注意点・カード見分け方のコツ】\n{current_prompt}\n上記を踏まえ、10枚のカード名、数字、向きを出力してください。"
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=[final_prompt, img],
            config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json", response_schema=TarotReading)
        )
        return json.loads(response.text)
    except Exception as e:
        st.error("現在、AIサーバーが大変混み合っており画像解析に失敗しました。数分後にもう一度お試しください。")
        st.stop()

def update_learning_prompt(differences, img):
    client = genai.Client(api_key=API_KEY)
    current_file = "current_prompt.txt"
    current_prompt = ""
    if os.path.exists(current_file):
        with open(current_file, "r", encoding="utf-8") as f:
            current_prompt = f.read()
    error_report = ""
    for diff in differences:
        error_report += f"- {diff['ポジション']}: 正解は {diff['正解']} ですが、AIは {diff['AIの判定']} と誤認しました。\n"
    meta_prompt = f"あなたは優秀なAIプロンプトエンジニアです。\nタロットカードの画像認識において、ユーザーから以下の修正指示（エラー報告）がありました。\n[現在の見分け方のコツ]\n{current_prompt}\n[ユーザーからのエラー報告（正解データ）]\n{error_report}\nこの間違いを二度と繰り返さないように、[現在の見分け方のコツ]をアップデートしてください。\n出力は **新しい見分け方のコツのテキストのみ** としてください。"
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest", contents=[meta_prompt, img], config=types.GenerateContentConfig(temperature=0.2)
        )
        with open(current_file, "w", encoding="utf-8") as f:
            f.write(response.text.strip())
        return True
    except Exception as e:
        st.toast("サーバー混雑のため、今回のAI自動学習はスキップされました。")
        return False

# --- PDF鑑定書 ---
def generate_pdf_report(chat_history, df, img):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=25*mm, bottomMargin=25*mm)
    
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
    
    deep_teal = colors.HexColor('#133B3A')
    champagne_gold = colors.HexColor('#C5A059')
    dark_slate = colors.HexColor('#2C3E50')
    delicate_gray = colors.HexColor('#E0EBEB')

    banner_title_style = ParagraphStyle(name='BannerTitle', fontName='HeiseiMin-W3', fontSize=26, leading=34, alignment=1, textColor=colors.white, spaceAfter=8)
    banner_sub_style = ParagraphStyle(name='BannerSubTitle', fontName='HeiseiMin-W3', fontSize=12, leading=16, alignment=1, textColor=champagne_gold)
    
    heading_style = ParagraphStyle(name='Heading', fontName='HeiseiMin-W3', fontSize=16, spaceAfter=8, spaceBefore=35, textColor=deep_teal, alignment=1)
    chat_heading_style = ParagraphStyle(name='ChatHeading', fontName='HeiseiMin-W3', fontSize=13, leading=18, textColor=deep_teal, spaceBefore=20, spaceAfter=8)
    
    user_style = ParagraphStyle(name='User', fontName='HeiseiMin-W3', fontSize=10.5, leading=20, textColor=colors.darkgray, leftIndent=15)
    nabi_style = ParagraphStyle(name='Nabi', fontName='HeiseiMin-W3', fontSize=11.5, leading=24, textColor=dark_slate, leftIndent=15)

    elements = []
    
    banner_content = [
        [Paragraph("Nabi AI Tarot Reader", banner_title_style)],
        [Paragraph("- 鑑定証明書 -", banner_sub_style)]
    ]
    title_table = Table(banner_content, colWidths=[170*mm])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), deep_teal),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 25),
        ('BOTTOMPADDING', (0,0), (-1,-1), 25),
        ('BOX', (0,0), (-1,-1), 0.5, dark_slate),
    ]))
    elements.append(title_table)
    elements.append(Spacer(1, 35))
    
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    aspect = img.height / float(img.width)
    img_w = 180
    img_h = 180 * aspect
    elements.append(RLImage(img_buffer, width=img_w, height=img_h))
    elements.append(Spacer(1, 25))
    
    elements.append(Paragraph("展開されたカード", heading_style))
    elements.append(HRFlowable(width="30%", thickness=0.5, color=champagne_gold, spaceAfter=20, hAlign='CENTER'))
    
    table_data = [['位置', 'カード名', '向き', '数字']]
    for index, row in df.iterrows():
        pos_num = row['ポジション'].replace('pos_', 'Pos.')
        table_data.append([pos_num, row['カード名'], row['向き'], row['数字']])
        
    card_table = Table(table_data, colWidths=[30*mm, 70*mm, 35*mm, 25*mm])
    card_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), deep_teal),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiMin-W3'),   
        ('FONTSIZE', (0, 0), (-1, -1), 10.5),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, delicate_gray), 
    ]))
    elements.append(card_table)
    elements.append(Spacer(1, 30))
    
    elements.append(Paragraph("鑑定セッション記録", heading_style))
    elements.append(HRFlowable(width="30%", thickness=0.5, color=champagne_gold, spaceAfter=25, hAlign='CENTER'))
    
    for msg in chat_history:
        if msg.get("is_system"):
            continue 
        
        if msg["role"] == "user":
            elements.append(Paragraph("<b>【ご相談内容】</b>", ParagraphStyle(name='U_Head', fontName='HeiseiMin-W3', fontSize=10, textColor=colors.gray)))
            elements.append(Spacer(1, 5))
            clean_text = msg["content"].replace('\n', '<br/>')
            elements.append(Paragraph(clean_text, user_style))
            elements.append(Spacer(1, 20))
        else:
            elements.append(Paragraph("<b>【占い師 Nabi】</b>", ParagraphStyle(name='N_Head', fontName='HeiseiMin-W3', fontSize=12, textColor=champagne_gold)))
            elements.append(Spacer(1, 10))
            
            lines = msg["content"].split('\n')
            para_buffer = []
            
            def flush_buffer():
                if para_buffer:
                    p_text = "<br/>".join(para_buffer)
                    p_text = re.sub(r'\*\*(.*?)\*\*', r'<font color="#C5A059">\1</font>', p_text)
                    p_text = re.sub(r'\*(.*?)\*', r'<font color="#C5A059">\1</font>', p_text)
                    elements.append(Paragraph(p_text, nabi_style))
                    elements.append(Spacer(1, 8))
                    para_buffer.clear()

            for line in lines:
                line = line.strip()
                match = re.match(r'^(#{1,6})\s+(.*)', line)
                if match:
                    flush_buffer()
                    h_text = match.group(2)
                    elements.append(Paragraph(f"■ {h_text}", chat_heading_style))
                elif line == "":
                    flush_buffer()
                else:
                    para_buffer.append(line)
            flush_buffer() 
            
            elements.append(HRFlowable(width="80%", thickness=0.3, color=delicate_gray, spaceBefore=25, spaceAfter=30, hAlign='CENTER'))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==========================================
# 3. 状態管理（Session State）
# ==========================================
if "step" not in st.session_state:
    st.session_state.step = "upload"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ==========================================
# 4. メインUIの構築
# ==========================================
st.markdown("""
<div class="premium-title-banner">
    <h1>Nabi AI Tarot Reader</h1>
    <p>- 鑑定証明書 -</p>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------
# STEP 1: 画像のアップロード
# ------------------------------------------
if st.session_state.step == "upload":
    st.write("ケルト十字展開のタロット画像をアップロードしてください。")
    uploaded_file = st.file_uploader("画像を選択...", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        # --- 画像回転のためのメモリ管理 ---
        # 新しいファイルがアップロードされた場合、初期状態の画像をセットする
        if "uploaded_filename" not in st.session_state or st.session_state.uploaded_filename != uploaded_file.name:
            st.session_state.uploaded_filename = uploaded_file.name
            st.session_state.current_image = PIL.Image.open(uploaded_file)
        
        st.image(st.session_state.current_image, caption="現在の画像", width="stretch")
        
        # エレガントな注意書き
        st.markdown("<p style='font-size:0.9em; color:#7F8C8D; margin-bottom: 20px;'>※ 画像が横向きの場合は、正しい向きに回転してから解析を実行してください。</p>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("画像を90度回転する"):
                # expand=True で画像が見切れないようにキャンバスを拡張して回転（右回り）
                st.session_state.current_image = st.session_state.current_image.rotate(-90, expand=True)
                st.rerun() # 画面を再描画して回転した画像を表示
                
        with col2:
            if st.button("AIでカードを解析する", type="primary"):
                with st.spinner("Nabiが画像を解析中..."):
                    # 解析には「回転済み」の画像を渡す
                    raw_data = analyze_image(st.session_state.current_image)
                    df_data = []
                    positions = [f"pos_{i}" for i in range(1, 11)]
                    for pos in positions:
                        card = raw_data.get(pos, {})
                        df_data.append({
                            "ポジション": pos,
                            "カード名": card.get("name", ""),
                            "数字": card.get("number", ""),
                            "向き": card.get("orientation", "")
                        })
                    st.session_state.original_df = pd.DataFrame(df_data)
                    # 次のステップやPDF出力に引き継ぐため、最終的な画像を保存
                    st.session_state.image = st.session_state.current_image 
                    st.session_state.step = "verify"
                    st.rerun()

# ------------------------------------------
# STEP 2: 解析結果の確認と修正
# ------------------------------------------
elif st.session_state.step == "verify":
    st.markdown("### 解析結果の確認")
    st.write("Nabiが読み取ったカード情報です。間違っている箇所があれば、表のセルをクリックして直接修正してください。")
    
    edited_df = st.data_editor(
        st.session_state.original_df, 
        width="stretch", 
        hide_index=True,
        column_config={"ポジション": st.column_config.Column(disabled=True)},
        height=400 
    )
    
    st.warning("確認が完了したら、下のボタンを押して占いを開始してください。（修正した内容はNabiが自動学習します）")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("画像を選び直す"):
            st.session_state.step = "upload"
            st.rerun()
    with col2:
        if st.button("占いを開始する", type="primary"):
            differences = []
            for index, row in edited_df.iterrows():
                orig_row = st.session_state.original_df.iloc[index]
                if (row["カード名"] != orig_row["カード名"] or row["数字"] != orig_row["数字"] or row["向き"] != orig_row["向き"]):
                    differences.append({
                        "ポジション": row["ポジション"],
                        "正解": {"name": row["カード名"], "number": row["数字"], "orientation": row["向き"]},
                        "AIの判定": {"name": orig_row["カード名"], "number": orig_row["数字"], "orientation": orig_row["向き"]}
                    })
            if differences:
                with st.spinner("修正内容をもとに、Nabiが見分け方のコツを学習・アップデート中..."):
                    success = update_learning_prompt(differences, st.session_state.image)
                    if success:
                        st.success("Nabiがあなたの修正から学習しました。")
            
            st.session_state.final_data = edited_df
            st.session_state.step = "chat"
            st.rerun()

# ------------------------------------------
# STEP 3: AI占いチャット
# ------------------------------------------
elif st.session_state.step == "chat":
    st.markdown("### 占いセッション")
    client = genai.Client(api_key=API_KEY)
    
    if not st.session_state.chat_history:
        confirmed_text = "以下のカード展開（ケルト十字）をもとに占いをしてください。\n\n"
        for index, row in st.session_state.final_data.iterrows():
            confirmed_text += f"- {row['ポジション']}: {row['カード名']} (数字: {row['数字']}, {row['向き']})\n"
        
        tarot_prompt_file = "tarot_prompt.txt"
        tarot_base_prompt = ""
        if os.path.exists(tarot_prompt_file):
            with open(tarot_prompt_file, "r", encoding="utf-8") as f:
                tarot_base_prompt = f.read()
        else:
            tarot_base_prompt = "あなたの名前は「Nabi」です。プロのタロット占い師として振る舞ってください。\nまずは優しく挨拶し、ユーザーに「何について占いたいか」を尋ねてください。"
            
        system_instruction = f"""
        {tarot_base_prompt}
        
        【今回の展開内容】
        {confirmed_text}
        """
        
        with st.spinner("Nabiが準備中..."):
            try:
                contents = [types.Content(role="user", parts=[types.Part.from_text(text=system_instruction)])]
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=contents,
                    config=types.GenerateContentConfig(temperature=0.7)
                )
                ai_text = response.text
            except Exception:
                ai_text = "現在AIサーバーが混み合っているため、最初の挨拶をスキップしました。そのまま占いたい内容を送信してください。"

            st.session_state.chat_history.append({"role": "user", "content": system_instruction, "is_system": True})
            st.session_state.chat_history.append({"role": "model", "content": ai_text, "is_system": False})

    for message in st.session_state.chat_history:
        if message.get("is_system"):
            continue 
        display_role = "assistant" if message["role"] == "model" else "user"
        with st.chat_message(display_role):
            st.markdown(message["content"])

    if prompt := st.chat_input("Nabiにメッセージを送信..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        
        st.session_state.chat_history.append({"role": "user", "content": prompt, "is_system": False})
        
        api_contents = []
        for msg in st.session_state.chat_history:
            api_contents.append(
                types.Content(role=msg["role"], parts=[types.Part.from_text(text=msg["content"])])
            )
        
        with st.chat_message("assistant"):
            with st.spinner("カードの声を聴いています..."):
                try:
                    response = client.models.generate_content(
                        model="gemini-flash-latest",
                        contents=api_contents,
                        config=types.GenerateContentConfig(temperature=0.7)
                    )
                    st.markdown(response.text)
                    st.session_state.chat_history.append({"role": "model", "content": response.text, "is_system": False})
                except Exception as e:
                    st.error("現在、サーバーが大変混み合っています。")
                    st.warning("数分ほど時間をおいてから、もう一度メッセージを送信してみてください。")
                    st.session_state.chat_history.pop()


# ==========================================
# 5. サイドバーの共通構築
# ==========================================
if st.session_state.step in ["verify", "chat"]:
    with st.sidebar:
        st.header("展開情報")
        st.image(st.session_state.image, caption="アップロード画像")
        st.subheader("カード一覧")
        
        display_df = st.session_state.final_data if st.session_state.step == "chat" else st.session_state.original_df
        for index, row in display_df.iterrows():
            pos_num = row['ポジション'].replace('pos_', '')
            num_text = f" / {row['数字']}" if row['数字'] != "-" else ""
            st.markdown(f"**[{pos_num}] {row['カード名']}**<br><span style='font-size:0.85em; color:#C5A059;'>{row['向き']}{num_text}</span>", unsafe_allow_html=True)
            
        st.divider() 
        
        if st.session_state.step == "chat":
            st.subheader("鑑定書の出力")
            st.write("これまでの鑑定結果をPDF形式でダウンロードできます。")
            
            pdf_data = generate_pdf_report(
                st.session_state.chat_history, 
                st.session_state.final_data, 
                st.session_state.image
            )
            
            st.download_button(
                label="鑑定書をダウンロード (PDF)",
                data=pdf_data,
                file_name="nabi_tarot_report.pdf",
                mime="application/pdf",
                type="primary"
            )
            st.divider()

        if st.button("リセットして最初から"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()