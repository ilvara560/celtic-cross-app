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

# --- 💎 プレミアム・ティファニーブルーUI用のカスタムCSS ---
custom_css = """
<style>
/* 全体の背景色とベース文字色 */
.stApp {
    background-color: #F4F9F9;
    color: #1C2833;
}

/* フォント設定（明朝体で高級感を演出） */
h1, h2, h3, .mincho {
    font-family: "Hiragino Mincho ProN", "Yu Mincho", serif !important;
}

/* 重厚なタイトルバナー */
.premium-title-banner {
    background-color: #13524E;
    border: 2px solid #D4AF37;
    padding: 35px 20px;
    text-align: center;
    margin-bottom: 30px;
    margin-top: 10px;
    border-radius: 4px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.15);
}
.premium-title-banner h1 {
    color: #FFFFFF !important;
    font-size: 2.2rem !important;
    padding: 0 !important;
    margin: 0 0 10px 0 !important;
    border: none !important;
}
.premium-title-banner p {
    color: #D4AF37 !important;
    font-size: 1.1rem !important;
    margin: 0 !important;
    font-family: "Hiragino Mincho ProN", "Yu Mincho", serif !important;
}

/* セクション見出し（帯デザイン） */
h3 {
    background-color: #1E847F !important;
    color: #FFFFFF !important;
    padding: 12px 15px !important;
    border-radius: 3px;
    text-align: center;
    font-size: 1.3rem !important;
    margin-top: 25px !important;
    margin-bottom: 25px !important;
    box-shadow: 0 2px 5px rgba(30, 132, 127, 0.3);
}

/* 💎 ファイルアップローダー（画像選択枠）のプレミアム化 */
[data-testid="stFileUploader"] label p {
    color: #1E847F !important; /* 「画像を選択...」をティファニーブルーに */
    font-weight: bold !important;
    font-size: 1.1rem !important;
}
[data-testid="stFileUploadDropzone"] {
    background-color: #FFFFFF !important; /* 背景を真っ白にして清潔感を出す */
    border: 2px dashed #81D8D0 !important; /* 枠線を明るいティファニーブルーの点線に */
    border-radius: 8px !important;
}
[data-testid="stFileUploadDropzone"] * {
    color: #1C2833 !important; /* 中の案内テキスト（200MB etc.）を濃いグレーに */
}
[data-testid="stFileUploadDropzone"] button {
    background-color: #1E847F !important;
    border: none !important;
    border-radius: 4px !important;
}
[data-testid="stFileUploadDropzone"] button,
[data-testid="stFileUploadDropzone"] button * {
    color: #FFFFFF !important; /* Uploadボタンの文字は白 */
}
[data-testid="stFileUploadDropzone"] button:hover {
    background-color: #13524E !important;
}
[data-testid="stFileUploadDropzone"] button:hover,
[data-testid="stFileUploadDropzone"] button:hover * {
    color: #D4AF37 !important; /* ホバー時にゴールド文字 */
}

/* サイドバーのデザイン */
[data-testid="stSidebar"] {
    background-color: #1C2833 !important;
}
[data-testid="stSidebar"] * {
    color: #E8F6F5 !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    background-color: transparent !important;
    color: #81D8D0 !important;
    border-bottom: 1px solid #1E847F !important;
    padding: 0 0 8px 0 !important;
    text-align: left;
    box-shadow: none !important;
    margin-top: 15px !important;
}
[data-testid="stSidebar"] hr {
    border-color: #1E847F;
}

/* プライマリボタン */
div.stButton > button[kind="primary"] {
    background-color: #1E847F !important;
    color: white !important;
    border: 1px solid #1E847F !important;
    border-radius: 4px !important;
    font-weight: bold;
    transition: all 0.3s ease;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #13524E !important;
    border-color: #D4AF37 !important;
    color: #D4AF37 !important;
    box-shadow: 0 4px 12px rgba(212, 175, 55, 0.25) !important;
}

/* セカンダリボタン */
div.stButton > button[kind="secondary"] {
    color: #1E847F !important;
    border: 1px solid #1E847F !important;
    border-radius: 5px !important;
    background-color: transparent !important;
    transition: all 0.3s;
}
div.stButton > button[kind="secondary"]:hover {
    border-color: #D4AF37 !important;
    color: #D4AF37 !important;
    background-color: rgba(212, 175, 55, 0.05) !important;
}

/* 注意書き（アラート枠）のエレガント化 */
div[data-testid="stAlert"] {
    background-color: rgba(30, 132, 127, 0.05);
    border: 1px solid #1E847F;
    color: #1C2833;
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
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    
    dark_tiffany = colors.HexColor('#1E847F')
    deep_tiffany = colors.HexColor('#13524E')
    deep_slate = colors.HexColor('#1C2833')
    light_bg = colors.HexColor('#F4F9F9')
    accent_gold = colors.HexColor('#D4AF37')

    banner_title_style = ParagraphStyle(name='BannerTitle', fontName='HeiseiMin-W3', fontSize=28, leading=34, alignment=1, textColor=colors.white)
    banner_sub_style = ParagraphStyle(name='BannerSubTitle', fontName='HeiseiMin-W3', fontSize=14, leading=20, alignment=1, textColor=accent_gold)
    
    heading_style = ParagraphStyle(name='Heading', fontName='HeiseiKakuGo-W5', fontSize=15, spaceAfter=15, spaceBefore=25, textColor=colors.white, backColor=dark_tiffany, borderPadding=8, alignment=1)
    chat_heading_style = ParagraphStyle(name='ChatHeading', fontName='HeiseiKakuGo-W5', fontSize=12.5, leading=16, textColor=dark_tiffany, spaceBefore=15, spaceAfter=8)
    user_style = ParagraphStyle(name='User', fontName='HeiseiKakuGo-W5', fontSize=10.5, leading=18, textColor=colors.darkslategray, leftIndent=15)
    nabi_style = ParagraphStyle(name='Nabi', fontName='HeiseiMin-W3', fontSize=11.5, leading=22, textColor=deep_slate, leftIndent=15)

    elements = []
    
    banner_content = [
        [Paragraph("Nabi AI Tarot Reader", banner_title_style)],
        [Spacer(1, 5)],
        [Paragraph("- 鑑定証明書 -", banner_sub_style)]
    ]
    title_table = Table(banner_content, colWidths=[170*mm])
    title_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), deep_tiffany),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 18),
        ('BOTTOMPADDING', (0,0), (-1,-1), 18),
        ('BOX', (0,0), (-1,-1), 1.5, accent_gold),
        ('INNERGRID', (0,0), (-1,-1), 0, colors.transparent),
    ]))
    elements.append(title_table)
    elements.append(Spacer(1, 25))
    
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    aspect = img.height / float(img.width)
    img_w = 200
    img_h = 200 * aspect
    elements.append(RLImage(img_buffer, width=img_w, height=img_h))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("展開されたカード", heading_style))
    
    table_data = [['位置', 'カード名', '向き', '数字']]
    for index, row in df.iterrows():
        pos_num = row['ポジション'].replace('pos_', 'Pos.')
        table_data.append([pos_num, row['カード名'], row['向き'], row['数字']])
        
    card_table = Table(table_data, colWidths=[30*mm, 70*mm, 35*mm, 25*mm])
    card_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), dark_tiffany),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'HeiseiKakuGo-W5'), 
        ('FONTNAME', (0, 1), (-1, -1), 'HeiseiMin-W3'),   
        ('FONTSIZE', (0, 0), (-1, -1), 10.5),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_bg])
    ]))
    elements.append(card_table)
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("鑑定セッション記録", heading_style))
    elements.append(Spacer(1, 10))
    
    for msg in chat_history:
        if msg.get("is_system"):
            continue 
        
        if msg["role"] == "user":
            elements.append(Paragraph("<b>【ご相談内容】</b>", ParagraphStyle(name='U_Head', fontName='HeiseiKakuGo-W5', fontSize=10, textColor=colors.gray)))
            elements.append(Spacer(1, 5))
            clean_text = msg["content"].replace('\n', '<br/>')
            elements.append(Paragraph(clean_text, user_style))
            elements.append(Spacer(1, 15))
        else:
            elements.append(Paragraph("<b>【占い師 Nabi】</b>", ParagraphStyle(name='N_Head', fontName='HeiseiMin-W3', fontSize=13, textColor=dark_tiffany)))
            elements.append(Spacer(1, 8))
            
            lines = msg["content"].split('\n')
            para_buffer = []
            
            def flush_buffer():
                if para_buffer:
                    p_text = "<br/>".join(para_buffer)
                    p_text = re.sub(r'\*\*(.*?)\*\*', r'<font color="#1E847F">\1</font>', p_text)
                    p_text = re.sub(r'\*(.*?)\*', r'<font color="#1E847F">\1</font>', p_text)
                    elements.append(Paragraph(p_text, nabi_style))
                    elements.append(Spacer(1, 6))
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
            
            elements.append(HRFlowable(width="70%", thickness=0.5, color=dark_tiffany, spaceBefore=20, spaceAfter=25, hAlign='CENTER'))

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
        img = PIL.Image.open(uploaded_file)
        st.image(img, caption="アップロードされた画像", width="stretch")
        
        if st.button("AIでカードを解析する", type="primary"):
            with st.spinner("Nabiが画像を解析中..."):
                raw_data = analyze_image(img)
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
                st.session_state.image = img
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
            st.markdown(f"**[{pos_num}] {row['カード名']}**<br><span style='font-size:0.85em; color:#81D8D0;'>{row['向き']}{num_text}</span>", unsafe_allow_html=True)
            
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