from datetime import datetime

import pydeck as pdk
import streamlit as st
import base64
import os
import time
import re
import random
from datetime import timedelta
import json
import math

import requests
from urllib.parse import quote

from rag import SHORT_DO, POIS, STAY, TZ, llm_text, assess, concepts_in, generate, get_place, haversine_km, hours_note, quality, retrieve
from routing import MODES, clean_steps, compass, fmt_dist, get_route, nav_links, nearest_stop, order_nearest, places_along

st.set_page_config(page_title="Гид по Астане", page_icon="🧭", layout="wide", initial_sidebar_state="collapsed")

GROUP = {  # группа -> (эмодзи, цвет RGB)
    "Еда и кофе": ("", [232, 190, 90]), "Потусить": ("", [222, 110, 150]), "Культура": ("", [110, 160, 235]),
    "Прогулка": ("", [90, 200, 150]), "Развлечения": ("", [240, 150, 90]), "Шопинг": ("", [150, 210, 220]),
}
CAT_EMOJI = {"кофейня": "☕", "ресторан": "🍽️", "фастфуд": "🍔", "бар": "🍻", "клуб": "🪩", "караоке": "🎤",
             "кино": "🎬", "театр": "🎭", "музей": "🏛️", "галерея": "🖼️", "арт-пространство": "🎨", "парк": "🌳",
             "достопримечательность": "📸", "смотровая": "🌇", "тц": "🛍️", "боулинг": "🎳", "квесты": "🗝️",
             "игровой клуб": "🕹️", "развлечения": "🎡", "фудкорт": "🍟"}
BADGE = {"green": "🟢", "orange": "🟠", "red": "🔴", "gray": "⚪"}
START = {"Mega Silk Way": (51.0891, 71.4073), "Байтерек": (51.1283, 71.4305), "Хан Шатыр": (51.1325, 71.4039),
         "EXPO": (51.0894, 71.4167), "Набережная": (51.1262, 71.4470)}
# адрес точки старта и признаки адресов заведений, которые находятся прямо здесь (для них расстояние 0)
START_INFO = {"Mega Silk Way": ("проспект Кабанбай батыр, 62", ("silk way", "батыр даңғылы 62", "батыр, 62")),
              "Байтерек": ("улица Акмешит, 14 (монумент Байтерек)", ("байтерек",)),
              "Хан Шатыр": ("проспект Туран, 37", ("тұран даңғылы 37", "туран, 37", "туран даңғылы 37")),
              "EXPO": ("территория EXPO-2017, сфера Нур Алем", ("нур алем", "нұр әлем")),
              "Набережная": ("набережная реки Есиль, центр города", ())}
from scenarios import (ACCESS_CALL, BY_LABEL, CHALLENGES, DOG_CHECKLIST, DOG_TIPS, FORMAT_HINT, FORMATS, LEVELS, SCENARIOS, STORIES, TAG_ORDER, blurb, evening_line, icon_css, source_line, sunset, ui_tags, weather_summary)
EXAMPLES = ["Популярное кафе с видом на город",
            "Хочу что-то связанное с адреналином",
            "Места, где можно прийти с собакой"]
CAT_LABEL = {"тц": "ТРЦ", "кофейня": "Кафе и кофейни", "бар": "Бары", "ресторан": "Рестораны", "театр": "Театры",
             "кино": "Кино", "галерея": "Галереи", "музей": "Музеи", "парк": "Парки", "фастфуд": "Фастфуд",
             "развлечения": "Развлечения", "кулинария": "Кулинария"}
BY_ID = {p["id"]: p for p in POIS}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700;800&family=Manrope:wght@300;400;500;600;700&display=swap');
:root {--gold:#D4AF37; --champ:#E8D8A8; --ink:#EDE9DD; --muted:#98A6C0; --line:rgba(212,175,55,.22); --glass:rgba(255,255,255,.04);}
html, body, [class*="css"], .stApp {font-family:'Manrope',sans-serif; letter-spacing:.005em;}
.stApp {background: radial-gradient(1200px 600px at 12% -10%, rgba(45,95,210,.38), transparent 60%),
                    radial-gradient(900px 500px at 100% 0%, rgba(212,175,55,.08), transparent 55%), #060E24;}
header[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 4.5rem !important; max-width: 1280px;}
h1, h2, h3, h4 {font-family:'Playfair Display',serif !important; font-weight:600 !important; letter-spacing:.01em; color:var(--champ) !important;}
h2 {font-size:1.9rem !important;} h3 {font-size:1.35rem !important;} h4 {font-size:1.15rem !important; color:var(--gold) !important;}
.hero {position:relative; padding: 46px 48px; margin-bottom: 26px; border-radius: 28px; overflow:hidden;
  background: linear-gradient(135deg, rgba(20,48,120,.95) 0%, rgba(6,14,36,.97) 60%); border:1px solid var(--line);
  box-shadow: 0 30px 60px -30px rgba(0,0,0,.8), inset 0 1px 0 rgba(232,216,168,.12);}
.hero::after {content:""; position:absolute; right:-80px; top:-80px; width:340px; height:340px; border-radius:50%;
  background: radial-gradient(circle, rgba(212,175,55,.28), transparent 65%);}
.hero .eyebrow {font-size:.74rem; letter-spacing:.38em; text-transform:uppercase; color:var(--gold); margin-bottom:10px;}
.hero h1 {font-family:'Playfair Display',serif; font-size:3rem; font-weight:700; color:var(--champ); margin:0; padding:0; line-height:1.1;}
.hero .rule {width:64px; height:2px; background:linear-gradient(90deg,var(--gold),transparent); margin:16px 0;}
.hero p {margin:0; max-width:560px; font-weight:300; font-size:1.05rem; color:#C9D3E6; line-height:1.6;}
[data-testid="stCaptionContainer"], .stCaption {color:var(--muted) !important;}
[data-testid="stMetric"] {background:var(--glass); border:1px solid var(--line); border-radius:16px; padding:14px 18px;}
[data-testid="stMetricLabel"] {color:var(--muted) !important; text-transform:uppercase; font-size:.7rem; letter-spacing:.14em;}
[data-testid="stMetricValue"] {color:var(--champ) !important; font-family:'Playfair Display',serif; font-size:1.8rem; font-weight:700;}
[data-testid="stSidebar"] {background:#091330; border-right:1px solid var(--line);}
[data-testid="stSidebar"] h2 {font-size:1.5rem !important;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:20px !important; background:var(--glass);
  border:1px solid var(--line) !important; transition: all .25s ease; backdrop-filter: blur(6px);}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {border-color:rgba(212,175,55,.55) !important;
  box-shadow: 0 18px 40px -18px rgba(212,175,55,.35); transform: translateY(-3px);}
.stButton>button, .stLinkButton>a {border-radius:999px !important; font-weight:500; letter-spacing:.04em;
  background:transparent; border:1px solid var(--line); color:var(--ink); transition:.2s;}
.stButton>button:hover, .stLinkButton>a:hover {border-color:var(--gold); color:var(--gold); background:transparent;}
.stButton>button[kind="primary"], .stLinkButton>a[kind="primary"] {background:linear-gradient(135deg,#E8D8A8,#C79A2B); color:#1a1405 !important; border:0; font-weight:600;
  box-shadow:0 8px 20px -8px rgba(212,175,55,.6);}
.stButton>button[kind="primary"]:hover {filter:brightness(1.08); color:#1a1405 !important; background:linear-gradient(135deg,#E8D8A8,#C79A2B);}
.pill {display:inline-block; padding:3px 12px; margin:2px 6px 2px 0; border-radius:999px; font-size:.7rem; font-weight:500;
  letter-spacing:.1em; text-transform:uppercase; border:1px solid transparent;}
.tag {background:rgba(212,175,55,.08); color:var(--champ); border-color:var(--line);}
.good {background:rgba(60,190,130,.12); color:#7FE0B0; border-color:rgba(60,190,130,.4);}
.mid {background:rgba(230,170,50,.12); color:#EBC36B; border-color:rgba(230,170,50,.4);}
.bad {background:rgba(220,80,80,.12); color:#F09A9A; border-color:rgba(220,80,80,.4);}
.none {background:rgba(255,255,255,.05); color:var(--muted); border-color:rgba(255,255,255,.14);}
.best {border-radius:20px; padding:20px 24px; border:1px solid rgba(212,175,55,.5); margin-bottom:12px;
  background: linear-gradient(135deg, rgba(212,175,55,.14), rgba(212,175,55,.03)); color:var(--ink);}
.best .k {font-family:'Playfair Display',serif; font-size:1.7rem; font-weight:700; letter-spacing:.02em; color:var(--gold); line-height:1.1;}
.best .n {font-family:'Playfair Display',serif; font-size:1.5rem; font-weight:600; color:var(--champ); margin:6px 0 8px;}
.step {padding:7px 0; border-bottom:1px solid rgba(255,255,255,.08); color:#D5DCEA; font-weight:300;}
.stat {color:var(--gold); font-weight:600;} .acc {color:var(--champ); font-weight:500;}
.kicker {font-size:.68rem; letter-spacing:.28em; text-transform:uppercase; color:var(--gold);}
[data-testid="stMain"] div[data-testid="stForm"] {background:linear-gradient(135deg, rgba(212,175,55,.16), rgba(255,255,255,.03)); border:1px solid rgba(212,175,55,.55) !important;
  border-radius:22px; padding:18px 22px; box-shadow:0 24px 50px -24px rgba(212,175,55,.45), inset 0 1px 0 rgba(255,255,255,.08);}
[data-testid="stMain"] div[data-testid="stForm"] input {background:rgba(6,14,36,.88) !important; color:var(--ink) !important; font-size:1.1rem !important;
  border-radius:14px !important; border:1px solid rgba(212,175,55,.45) !important; height:3.2rem;}
[data-testid="stMain"] div[data-testid="stForm"] input:focus {border-color:var(--gold) !important; box-shadow:0 0 0 3px rgba(212,175,55,.25) !important;}
[data-testid="stMain"] div[data-testid="stForm"] button {background:linear-gradient(135deg,#E8D8A8,#C79A2B) !important; color:#1a1405 !important; font-weight:600;
  height:3.2rem; border:0 !important; letter-spacing:.08em; text-transform:uppercase; font-size:.85rem;}
[data-testid="stMain"] div[data-testid="stForm"] label p {color:var(--champ) !important; font-size:.72rem; letter-spacing:.24em; text-transform:uppercase;}
[data-testid="stSidebar"] div[data-testid="stForm"] {border:0 !important; padding:0 !important;}
[class*="st-key-ex_"] button[kind="primary"] {box-shadow:0 0 0 2px #FFE27A, 0 0 24px rgba(255,214,102,.75) !important; font-weight:700;}
hr {border-color:var(--line) !important;}
[data-testid="stExpander"] {border:1px solid var(--line) !important; border-radius:14px !important; background:var(--glass);}
.stAlert {border-radius:14px;}

/* ===== премиальные кнопки ===== */
.stButton > button, .stLinkButton > a, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {
  position:relative; border-radius:14px !important; font-weight:600; letter-spacing:.03em; transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease, background-position .4s ease;
}
.stButton > button[kind="secondary"], .stLinkButton > a:not([kind="primary"]) {
  background: linear-gradient(180deg, rgba(255,255,255,.075), rgba(255,255,255,.015)) !important;
  border:1px solid rgba(212,175,55,.32) !important; color:#F0E9D2 !important;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.10), 0 6px 18px -10px rgba(0,0,0,.7);
}
.stButton > button[kind="secondary"]:hover, .stLinkButton > a:not([kind="primary"]):hover {
  transform:translateY(-2px); border-color:#D4AF37 !important; color:#FFE9A8 !important;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.16), 0 14px 26px -12px rgba(212,175,55,.55), 0 0 0 1px rgba(212,175,55,.25);
}
.stButton > button[kind="primary"], .stLinkButton > a[kind="primary"] {
  background: linear-gradient(135deg,#F7E7B0 0%,#E2B84A 45%,#B98A1F 100%) !important; background-size:200% 200%;
  color:#1a1405 !important; border:1px solid rgba(255,236,170,.65) !important; text-shadow:0 1px 0 rgba(255,255,255,.35);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.55), inset 0 -2px 0 rgba(120,80,0,.25), 0 10px 24px -10px rgba(212,175,55,.75);
}
.stButton > button[kind="primary"]:hover, .stLinkButton > a[kind="primary"]:hover {
  transform:translateY(-2px); background-position:100% 50%; filter:brightness(1.05);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.65), inset 0 -2px 0 rgba(120,80,0,.25), 0 16px 30px -10px rgba(212,175,55,.9);
}
.stButton > button:active, .stLinkButton > a:active {transform:translateY(0) scale(.985);}
.stLinkButton > a:not([kind="primary"])::after {content:"↗"; margin-left:8px; opacity:.7; font-size:.9em;}
[class*="st-key-more_"] button::after {content:"→"; margin-left:8px; transition:transform .18s ease;}
[class*="st-key-more_"] button:hover::after {transform:translateX(4px);}
[class*="st-key-mc_"] button {min-height:2.4rem; font-size:.82rem; padding:.2rem .6rem;}
/* сценарные кнопки: карточки с иконкой */
[class*="st-key-ex_"] button {display:flex !important; flex-direction:column; align-items:center; justify-content:center; gap:6px;
  min-height:6.2rem !important; padding:.8rem .7rem !important; border-radius:18px !important;}
[class*="st-key-ex_"] button::before {content:""; width:30px; height:30px; background-repeat:no-repeat; background-position:center; background-size:contain; flex:0 0 auto;}
[class*="st-key-ex_"] button p {text-align:center; font-size:.84rem !important; letter-spacing:.02em;}
[class*="st-key-ex_"] button[kind="primary"] {box-shadow: inset 0 1px 0 rgba(255,255,255,.6), 0 0 0 2px #FFE27A, 0 0 28px rgba(255,214,102,.7) !important;}
[class*="st-key-ex_"] button[kind="primary"]::after {content:"✓"; position:absolute; top:8px; right:12px; font-size:.8rem; font-weight:800; color:#1a1405;}
.src {display:inline-block; font-size:.68rem; font-weight:500; letter-spacing:.06em; text-transform:uppercase; margin-right:8px; vertical-align:1px; opacity:.75;}
.src.data {color:#8FB8A5;}
.src.idea {color:#BFA970;}
.datastrip {border:1px solid var(--line); border-radius:14px; padding:10px 14px; margin:10px 0 12px; background:rgba(255,255,255,.03); color:#D5DCEA; font-size:.84rem; line-height:1.55;}
.datastrip b {color:var(--gold); letter-spacing:.1em; text-transform:uppercase; font-size:.7rem;}
.way {margin:8px 0 4px; padding:10px 14px; border:1px solid var(--line); border-radius:14px; background:rgba(255,255,255,.03); font-size:.88rem;}
.way b {color:var(--champ);}
.dgrid {margin:8px 0 6px; border-top:1px solid var(--line); padding-top:8px;}
.dgrid div {display:flex; gap:12px; font-size:.82rem; color:#C9D2E4; line-height:1.5; padding:2px 0;}
.dgrid span.l {flex:0 0 78px; color:var(--gold); font-size:.66rem; letter-spacing:.12em; text-transform:uppercase; padding-top:3px;}
.sec-filter {margin:4px 0 2px; color:var(--muted); font-size:.78rem; letter-spacing:.14em; text-transform:uppercase;}
[data-baseweb="button-group"] button {border-radius:999px !important;}
.best {backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); transition:transform .25s ease, box-shadow .25s ease;
  box-shadow:0 0 18px rgba(255,200,50,.28), inset 0 1px 0 rgba(255,255,255,.12);}
.best:hover {transform:translateY(-5px); box-shadow:0 18px 40px -14px rgba(255,190,40,.55), 0 0 22px rgba(255,200,50,.4);}
div[data-testid="stVerticalBlockBorderWrapper"] {backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px);}
.weather {margin:0 0 12px; padding:9px 16px; border-radius:14px; border:1px solid rgba(255,200,50,.35); background:rgba(255,255,255,.04);
  backdrop-filter:blur(10px); font-size:.9rem; color:#E9E3CF; box-shadow:0 0 15px rgba(255,215,0,.18);}
.weather.bad {border-color:rgba(120,190,255,.55); box-shadow:0 0 15px rgba(110,180,255,.3);}
.spin {text-align:center; font-family:'Playfair Display',serif; font-size:1.9rem; color:var(--champ); padding:16px; border:1px solid var(--line); border-radius:16px; background:rgba(255,255,255,.04);}
.spin.win {color:#FFD76A; border-color:#FFD76A; box-shadow:0 0 28px rgba(255,215,0,.55); animation:pop .5s ease;}
@keyframes pop {0% {transform:scale(.92);} 60% {transform:scale(1.04);} 100% {transform:scale(1);}}
.vgrid {display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; margin:8px 0 12px;}
.vcard {padding:12px 14px; border:1px solid var(--line); border-radius:16px; background:rgba(255,255,255,.04); backdrop-filter:blur(10px);
  box-shadow:0 0 14px rgba(255,200,50,.12); transition:transform .2s ease, box-shadow .2s ease;}
.vcard:hover {transform:translateY(-4px); box-shadow:0 12px 26px -12px rgba(255,200,50,.55);}
.vcard.sel {border-color:#FFD76A; box-shadow:0 0 22px rgba(255,215,0,.5);}
.vcard b {display:block; font-family:'Playfair Display',serif; color:var(--gold); font-size:1.12rem; margin-bottom:4px;}
.vcard span {font-size:.8rem; color:#CFD7E8; line-height:1.4;}
.vcard.pop {opacity:0; transform:scale(.55) translateY(18px); animation:popin .6s cubic-bezier(.2,1.5,.4,1) forwards;}
@keyframes popin {0% {opacity:0; transform:scale(.55) translateY(18px);} 70% {opacity:1; transform:scale(1.06) translateY(-2px);} 100% {opacity:1; transform:scale(1) translateY(0);}}
.rec {margin:10px 0; padding:10px 14px; border:1px solid var(--line); border-radius:14px; background:rgba(255,255,255,.035);}
.rec-h {font-family:'Playfair Display',serif; font-size:1.05rem; color:var(--champ); margin-bottom:4px;}
.rec-h span {font-family:'Manrope',sans-serif; font-size:.78rem; color:var(--muted); margin-left:6px;}
.kv {display:flex; gap:10px; font-size:.86rem; color:#E1E6F1; line-height:1.45; padding:2px 0;}
.kv .k {flex:0 0 84px; color:var(--gold); font-size:.66rem; letter-spacing:.12em; text-transform:uppercase; padding-top:3px;}
.kv .nd {color:#9AA6BF; font-style:normal;}
.fit {margin:8px 0; padding:8px 12px; border-left:2px solid var(--gold); font-size:.88rem; color:#D9DFEC;}
.evening {margin:10px 0; padding:14px 18px; border-radius:18px; border:1px solid rgba(255,200,50,.4); background:rgba(255,255,255,.04); backdrop-filter:blur(10px);
  box-shadow:0 0 18px rgba(255,200,50,.2);}
.evening .t {font-family:'Playfair Display',serif; color:var(--gold); font-size:1.25rem; margin-bottom:6px;}
.evening .row {padding:3px 0; font-size:.95rem; color:#EDE9DD;}
.st-key-lucky_btn button {min-height:3.4rem !important; font-size:1.05rem !important; font-weight:800 !important; letter-spacing:.06em;
  background:linear-gradient(135deg,#FFE066 0%,#FFC107 50%,#FF9800 100%) !important; color:#2a1700 !important;
  box-shadow:0 0 0 2px rgba(255,236,170,.7), 0 0 26px rgba(255,193,7,.65), inset 0 1px 0 rgba(255,255,255,.6) !important;}
.st-key-evening_btn button {min-height:3.4rem !important; font-size:1rem !important;}
@media (max-width: 768px) {
  .block-container {padding:3.2rem .7rem 2rem !important;}
  .hero {padding:18px 20px !important;} .hero h1 {font-size:1.7rem !important;}
  [data-testid="stHorizontalBlock"] {flex-wrap:wrap !important; gap:.5rem !important;}
  [data-testid="stHorizontalBlock"] > div {min-width:46% !important; flex:1 1 46% !important;}
  [class*="st-key-ex_"] button {min-height:5.2rem !important;}
  [class*="st-key-ex_"] button p {font-size:.78rem !important;}
}
.st-key-navbar-old {position:sticky; top:.6rem; z-index:60; padding:8px 10px; margin-bottom:12px; border-radius:18px; border:1px solid rgba(212,175,55,.35);
  background:rgba(8,16,40,.78); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); box-shadow:0 10px 30px -14px rgba(0,0,0,.8), 0 0 16px rgba(255,200,50,.14);}
.st-key-navbar button {min-height:2.6rem !important; min-width:3.2rem; font-size:1.5rem !important; line-height:1 !important; padding:.1rem .8rem !important;}
.st-key-navbar {display:flex; justify-content:flex-start; width:fit-content !important;}
[data-testid="stDeckGlJsonChart"], .sec, [class*="st-key-ex_"], [data-testid="stMain"] [data-testid="stForm"] {scroll-margin-top:84px;}
[data-testid="stExpandSidebarButton"] {position:fixed !important; top:14px; left:14px; z-index:100; width:auto; min-width:46px; height:46px; padding:0 16px; border-radius:14px;
  border:1px solid rgba(212,175,55,.55) !important; background:rgba(8,16,40,.85) !important; box-shadow:0 0 16px rgba(255,200,50,.2); display:flex !important; align-items:center; justify-content:center;}
[data-testid="stExpandSidebarButton"] > * {display:none !important;}
[data-testid="stExpandSidebarButton"]::after {content:"☰  Параметры"; font-size:1rem; font-weight:600; line-height:1; color:#E8C766; white-space:pre;}
@media (max-width:640px){[data-testid="stExpandSidebarButton"]::after {content:"☰";font-size:1.5rem;}}
[data-testid="stExpandSidebarButton"]:hover {border-color:#D4AF37 !important; box-shadow:0 0 22px rgba(255,200,50,.4);}
.params {margin:-4px 0 10px; font-size:.82rem; color:var(--muted);}
footer, [data-testid="stDecoration"], [data-testid="stToolbarActions"], [data-testid="stMainMenu"], [data-testid="stAppDeployButton"], .stAppDeployButton {display:none !important;}
.hero {padding:26px 34px !important; margin-bottom:16px !important; border-radius:22px !important;}
.hero::after, .hero .eyebrow, .hero .rule {display:none !important;}
.hero h1 {font-size:2.3rem !important;}
.hero p {margin-top:6px !important; font-size:1rem !important; color:#B9C5DC !important;}
.block-container {max-width:1180px !important;}
[class*="st-key-ex_"] button {min-height:3.6rem; height:auto; font-size:.86rem; padding:.45rem .7rem;}
[class*="st-key-ex_"] button p {white-space:normal !important; overflow:visible !important; text-overflow:clip !important; line-height:1.22 !important;}
.blurb {color:#CFD7E8; font-size:.9rem; line-height:1.5; margin:6px 0 8px;}
.blurb.story {font-size:.96rem; color:#EDE9DD; border-left:2px solid var(--gold); padding-left:12px; font-style:italic;}
.chip {display:inline-block; padding:2px 10px; margin:0 6px 6px 0; border-radius:999px; font-size:.72rem; font-weight:600; background:rgba(212,175,55,.14); color:var(--champ); border:1px solid var(--line);}
.panel-t {font-family:'Playfair Display',serif; font-size:1.5rem; color:var(--gold); margin:0;}
.why {color:#D9DFEC; font-size:.95rem; margin-top:8px; line-height:1.45;}
.meta {color:var(--muted); font-size:.86rem; margin:2px 0 6px;}
.steps {display:flex; flex-wrap:wrap; gap:8px 18px; margin-top:12px; font-size:.84rem; color:var(--muted);}
.steps b {display:inline-flex; width:20px; height:20px; align-items:center; justify-content:center; border-radius:50%; background:rgba(212,175,55,.18); color:#E8C766; margin-right:6px; font-size:.75rem;}
.params b {color:#E8C766; font-weight:600;}
.sec {font-family:'Playfair Display',serif; font-size:1.35rem; color:var(--champ); margin:26px 0 10px;}

.winner-k {scroll-margin-top:70px; font-size:.78rem; letter-spacing:.32em; text-transform:uppercase; color:var(--gold); margin:10px 0 -6px; animation:pop .7s cubic-bezier(.2,.8,.2,1) both;}
.winner-k + div [data-testid="stVerticalBlockBorderWrapper"], .winner-k ~ div [data-testid="stVerticalBlockBorderWrapper"]:first-of-type {animation:pop .8s cubic-bezier(.2,.8,.2,1) .1s both;}
[data-testid="stImage"] img {border-radius:14px; border:1px solid rgba(212,175,55,.35); box-shadow:0 10px 24px -14px rgba(0,0,0,.8);}
[class*="st-key-nm_"] button {justify-content:flex-start !important; padding:0 !important; min-height:0 !important; border:0 !important; background:transparent !important; box-shadow:none !important;}
[class*="st-key-nm_"] button p {font-family:'Playfair Display',serif; font-size:1.35rem !important; font-weight:600; color:var(--champ) !important; text-align:left; line-height:1.2; letter-spacing:0; transition:color .2s;}
[class*="st-key-nm_"] button:hover p {color:var(--gold) !important; text-decoration:underline; text-decoration-color:rgba(212,175,55,.6); text-underline-offset:4px;}
.srcbar {display:flex; flex-wrap:wrap; align-items:center; gap:6px 8px; margin:10px 0 6px; padding:8px 12px; border-radius:14px; border:1px solid rgba(212,175,55,.4);
  background:linear-gradient(135deg,rgba(212,175,55,.10),rgba(10,20,50,.5));}
.srcbar .sb {font-size:.7rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:#1a1405; background:linear-gradient(135deg,#F3DE9A,#D4AF37); padding:3px 10px; border-radius:999px;}
.srcbar .st {flex:1 1 220px; font-size:.76rem; color:var(--muted); line-height:1.35;}
.mini {border:1px solid rgba(212,175,55,.5); border-radius:22px; padding:18px 22px; margin:10px 0; background:linear-gradient(135deg,rgba(212,175,55,.10),rgba(10,20,50,.75)); animation:pop .8s cubic-bezier(.2,.8,.2,1) both;}
.mini .mk {font-size:.74rem; letter-spacing:.28em; text-transform:uppercase; color:var(--gold);}
.mini .mt {font-family:'Playfair Display',serif; font-size:1.5rem; color:var(--champ); margin:2px 0 12px;}
.ms {display:flex; gap:12px; align-items:flex-start; padding:6px 0;}
.mtime {min-width:46px; font-weight:700; color:var(--gold); font-size:.92rem; padding-top:4px;}
.mdot {min-width:26px; height:26px; border-radius:50%; background:linear-gradient(135deg,#F3DE9A,#D4AF37); color:#1a1405; font-weight:800; display:flex; align-items:center; justify-content:center; font-size:.82rem; margin-top:2px;}
.mbody b {font-family:'Playfair Display',serif; font-size:1.12rem; color:var(--champ); display:block;}
.mbody span {font-size:.78rem; color:var(--muted); display:block;} .mbody em {font-style:normal; font-size:.86rem; color:#DCE3F2; display:block; margin-top:3px;}
.mwalk {margin:0 0 0 58px; padding:2px 0 2px 12px; border-left:2px dashed rgba(212,175,55,.45); font-size:.76rem; color:var(--muted);}
.mini .mnote {margin-top:10px; font-size:.7rem; color:var(--muted);}
/* ---- «необычный» слой: северное сияние, звёзды, мерцающее золото, плавное появление ---- */
.stApp::before {content:""; position:fixed; inset:-20%; z-index:0; pointer-events:none; opacity:.55;
  background: radial-gradient(40% 35% at 20% 25%, rgba(70,120,255,.28), transparent 70%),
              radial-gradient(35% 30% at 80% 20%, rgba(212,175,55,.16), transparent 70%),
              radial-gradient(45% 40% at 60% 85%, rgba(120,70,220,.20), transparent 70%);
  filter: blur(30px); animation: aurora 22s ease-in-out infinite alternate;}
.stApp::after {content:""; position:fixed; inset:0; z-index:0; pointer-events:none; opacity:.55;
  background-image: radial-gradient(1.2px 1.2px at 12% 18%, #fff, transparent), radial-gradient(1px 1px at 78% 32%, #fff, transparent),
    radial-gradient(1.4px 1.4px at 45% 70%, #E8C766, transparent), radial-gradient(1px 1px at 90% 78%, #fff, transparent),
    radial-gradient(1.2px 1.2px at 30% 88%, #fff, transparent), radial-gradient(1px 1px at 62% 12%, #E8C766, transparent);
  animation: twinkle 6s ease-in-out infinite alternate;}
[data-testid="stMain"], [data-testid="stSidebar"] {position:relative; z-index:1;}
@keyframes aurora {0% {transform:translate3d(-3%,-2%,0) scale(1);} 100% {transform:translate3d(4%,3%,0) scale(1.12);}}
@keyframes twinkle {0% {opacity:.25;} 100% {opacity:.7;}}
@keyframes rise {from {opacity:0; transform:translateY(16px);} to {opacity:1; transform:none;}}
@keyframes shine {to {background-position:200% center;}}
.hero {animation: rise .7s ease both; border:1px solid rgba(212,175,55,.35) !important;
  box-shadow: 0 24px 60px -28px rgba(0,0,0,.9), 0 0 40px -10px rgba(212,175,55,.25), inset 0 1px 0 rgba(255,255,255,.08);}
.hero h1 {background:linear-gradient(100deg,#E8D9A8 0%,#D4AF37 25%,#FFF3C4 50%,#D4AF37 75%,#E8D9A8 100%); background-size:200% auto;
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; color:transparent; animation: shine 6s linear infinite;}
.hero .steps span {padding:5px 12px 5px 6px; border-radius:999px; background:rgba(255,255,255,.05); border:1px solid rgba(212,175,55,.2);}
[class*="st-key-ex_"] {animation: rise .6s ease both;}
[class*="st-key-ex_"]:nth-of-type(2) {animation-delay:.08s;}
[class*="st-key-ex_"] button {transition: transform .25s cubic-bezier(.2,.8,.2,1), box-shadow .25s ease, border-color .25s ease !important;}
[class*="st-key-ex_"] button:hover {transform: translateY(-6px) scale(1.03); box-shadow:0 18px 34px -14px rgba(255,190,40,.55), 0 0 24px rgba(255,200,50,.3) !important; border-color:#D4AF37 !important;}
[class*="st-key-ex_"] button:active {transform: translateY(-1px) scale(.99);}
.st-key-lucky_btn button {background-size:200% auto !important; animation: shine 4s linear infinite; letter-spacing:.06em;}
.st-key-lucky_btn button:hover {transform: translateY(-3px) scale(1.01); box-shadow:0 0 34px rgba(255,200,50,.6) !important;}
.best, .rec, .vcard, .dgrid {animation: rise .6s ease both;}
.sec {position:relative; padding-left:18px;}
.sec::before {content:""; position:absolute; left:0; top:.3em; bottom:.3em; width:4px; border-radius:4px; background:linear-gradient(180deg,#FFF3C4,#D4AF37,transparent);}
[data-testid="stTextInput"] input:focus {box-shadow:0 0 0 2px rgba(212,175,55,.55), 0 0 24px rgba(212,175,55,.25) !important;}
::-webkit-scrollbar {width:10px;} ::-webkit-scrollbar-thumb {background:linear-gradient(#D4AF37,#8A6D1D); border-radius:10px;} ::-webkit-scrollbar-track {background:#060E24;}

/* ---- вступительная анимация: три волны: начало (шапка), середина (сценарии), конец (кнопка и поиск) ---- */
@keyframes pop {0% {opacity:0; transform:translateY(28px) scale(.94); filter:blur(5px);} 100% {opacity:1; transform:none; filter:none;}}
@keyframes fadeUp {from {opacity:0; transform:translateY(18px);} to {opacity:1; transform:none;}}
.hero {animation: pop .7s cubic-bezier(.2,.8,.2,1) .1s both;}
.hero h1 {animation: fadeUp .7s ease .22s both, shine 6s linear 1.2s infinite;}
.hero p {animation: fadeUp .7s ease .34s both;}
.st-key-ex_view {animation: pop .7s cubic-bezier(.2,.8,.2,1) .90s both;}
.st-key-ex_adrenaline {animation: pop .7s cubic-bezier(.2,.8,.2,1) .98s both;}
.st-key-ex_dog {animation: pop .7s cubic-bezier(.2,.8,.2,1) 1.06s both;}
.st-key-ex_access {animation: pop .7s cubic-bezier(.2,.8,.2,1) 1.14s both;}
.st-key-ex_birthday {animation: pop .7s cubic-bezier(.2,.8,.2,1) 1.22s both;}
.st-key-lucky_btn {animation: pop .7s cubic-bezier(.2,.8,.2,1) 1.55s both;}
[data-testid="stMain"] [data-testid="stForm"] {animation: pop .7s cubic-bezier(.2,.8,.2,1) .55s both;}
[data-testid="stExpandSidebarButton"] {animation: pop .7s cubic-bezier(.2,.8,.2,1) .1s both;}
@media (prefers-reduced-motion: reduce) {*, *::before, *::after {animation:none !important; transition:none !important;}}
</style>
<div class="hero"><h1>Гид по Астане</h1><p>Скажите, чего хочется — подберём место, объясним почему и покажем дорогу</p></div>
""", unsafe_allow_html=True)

st.markdown(f"<style>{icon_css()}</style>", unsafe_allow_html=True)
ss = st.session_state
ss.setdefault("query", st.query_params.get("q", ""))
ss.setdefault("selected", None)
ss.setdefault("route", [])
ss.setdefault("answers", {})
ss.setdefault("mv", {})
NAV = [("Сценарии", "scen"), ("Поиск", "search"), ("Карта", "map"), ("Места", "places"), ("Маршрут", "route")]
pop = st.sidebar  # параметры — в левой панели, открывается кнопкой ☰


@st.cache_data(show_spinner=False, ttl=900)
def get_weather():
    try:
        c = requests.get("https://api.open-meteo.com/v1/forecast", timeout=8, params={
            "latitude": 51.13, "longitude": 71.43, "current": "temperature_2m,wind_speed_10m,precipitation,weather_code",
            "wind_speed_unit": "ms", "timezone": "Asia/Almaty"}).json()["current"]
        return dict(t=c["temperature_2m"], wind=c["wind_speed_10m"], pr=c["precipitation"], code=c["weather_code"])
    except Exception:
        return None


weather_bad, weather_text = weather_summary(get_weather())
ss.setdefault("scen_browse", False)  # «Все места» внутри сценария
ss.setdefault("show_all", False)  # вид каждой карты: (режим, счётчик перезапуска)

# ---------------- боковая панель ----------------
@st.cache_data(show_spinner=False, ttl=3600)
def geocode_place(q):
    """Место или адрес, которого нет в списке: сначала ищем среди наших заведений, затем в OpenStreetMap (только Астана)."""
    ql = q.strip().lower()
    for p in POIS:
        if len(ql) >= 3 and (ql in p["name"].lower() or p["name"].lower() in ql):
            return dict(lat=p["lat"], lon=p["lon"], label=p["name"], addr=p["address"], here=((p["address"] or "").lower(),) if p["address"] else ())
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search", timeout=12, headers={"User-Agent": "astana-walk-guide-hackathon/1.0"},
                         params={"q": f"{q}, Астана", "format": "json", "limit": 1, "accept-language": "ru",
                                 "viewbox": "71.30,51.22,71.55,51.03", "bounded": 1}).json()
        if r:
            return dict(lat=float(r[0]["lat"]), lon=float(r[0]["lon"]), label=q.strip(), addr=", ".join(r[0]["display_name"].split(", ")[:3]), here=())
    except Exception:
        pass
    return None


@st.cache_data(show_spinner=False)
def tags_for(pid):
    p = BY_ID[pid]
    s = nearest_stop("lrt", p["lat"], p["lon"])
    return ui_tags(p, s[1] if s else None)


HAN = "Хан Шатыр"
only_rated = True  # в выдаче только места с оценкой 2GIS (основа демо)
with pop:
    OTHER = "Другое"
    _sel = st.selectbox("Я сейчас возле", list(START) + [OTHER], index=None, placeholder="Не выбрано — покажем весь город")
    place = _sel or OTHER  # ничего не выбрано = без привязки к точке (весь город)
    custom_place = ""
    if _sel == OTHER:  # своё место: открывается поле для ввода названия или адреса
        custom_place = st.text_input("Место или адрес", placeholder="например: Достык 5, Сарыарка, EXPO…",
                                     help="Поиск пойдёт от этого места. Название уходит в OpenStreetMap для определения координат.")
    elif _sel:
        st.caption(f"Адрес: {START_INFO[place][0]}")
    with st.form("criteria", border=False):
        minutes = st.slider("Времени, мин", 15, 240, 90, 15)
        radius = st.slider("Радиус, км", 0.5, 10.0, 2.0, 0.5, help="По умолчанию 2 км; можно расширить до 10 км")
        _cnt = {}
        for _p in POIS:
            if _p["rating"]:
                _cnt[_p["category"]] = _cnt.get(_p["category"], 0) + 1
        cats = st.multiselect("Категории", sorted(_cnt, key=lambda c: -_cnt[c]),
                              format_func=lambda c: CAT_LABEL.get(c, c.capitalize()),
                              placeholder="Все категории")
        gems = False  # переключатель «Без туристов» убран из интерфейса
        mode = st.selectbox("Как передвигаетесь", list(MODES), format_func=lambda m: MODES[m],
                            index=list(MODES).index(st.query_params.get("mode")) if st.query_params.get("mode") in MODES else 0)
        with st.expander("Дополнительно"):
            min_rating = st.slider("Мин. рейтинг", 0.0, 5.0, 0.0, 0.5)
            sort = st.radio("Сортировать", ["Лучшее", "Ближе", "Рейтинг"], horizontal=True)
            group_n = st.slider("Нас человек", 1, 20, 1, help="Для компании от 3 человек подбираются места с большими залами и активностями")
            top_k = st.slider("Сколько мест", 3, 12, 8)
        done = st.form_submit_button("Готово", type="primary", use_container_width=True)
    if done:  # сворачиваем левую панель: «нажимаем» на её кнопку закрытия
        st.iframe("<script>(function(){try{const d=window.parent.document;let n=0;const go=()=>{"
                  "const b=d.querySelector('[data-testid=\"stSidebarCollapseButton\"] button')||d.querySelector('[data-testid=\"stSidebarHeader\"] button');"
                  "if(b){b.click();}else if(++n<6){setTimeout(go,250);}};setTimeout(go,200);}catch(e){}})();</script>", height=1)
    lat, lon = START[HAN] if place == OTHER else START[place]
    start_name, start_addr, here_keys = (HAN, START_INFO[HAN][0], START_INFO[HAN][1]) if place == OTHER else (place, START_INFO[place][0], START_INFO[place][1])
    anywhere = place == OTHER and not custom_place.strip()
    if anywhere:
        start_name, start_addr = "весь город", "без привязки к точке"
    if place == OTHER:
        if not custom_place.strip():
            if _sel:
                st.caption("Можно ничего не вводить — покажем все заведения города.")
        else:
            _f = geocode_place(custom_place)
            if _f:
                lat, lon, start_name, start_addr, here_keys = _f["lat"], _f["lon"], _f["label"], _f["addr"] or "адрес по данным карты", _f["here"]
                st.success(f"Ищем от: {start_name}" + (f" ({start_addr})" if start_addr else ""))
            else:
                st.warning("Место не найдено в Астане — ищем от Хан Шатыра.")
    st.caption("Локация нужна только для расстояний и не сохраняется.")
# ---------------- ввод ----------------
BADGES = {"вид": "С видом", "адреналин": "Адреналин", "с собакой": "С собакой", "доступно для колясок": "Доступно", "праздник": "Для праздника"}
base_now = datetime.now(TZ)
search_slot = st.container()  # строка поиска живёт сразу под шапкой, хотя обрабатывается ниже по коду
for col, sc in zip(st.columns(len(SCENARIOS)), SCENARIOS):
    active = ss.query == sc["label"] and not ss.show_all  # кнопка «горит», пока мы в этом сценарии
    if col.button(sc["label"], use_container_width=True, type="primary" if active else "secondary", key=f"ex_{sc['key']}"):
        # повторное нажатие на горящую кнопку гасит её и сбрасывает поиск
        ss.query, ss.selected, ss.show_all, ss.scen_browse = ("" if active else sc["label"]), None, False, False
        ss.fire_balloons = sc["key"] == "birthday" and not active
        ss.fx = sc["key"] if (sc["key"] in ("dog", "adrenaline") and not active) else None
        st.rerun()

wb = weather_bad
WALK_CATS = ["музей", "галерея", "тц", "кино", "развлечения", "театр"] if wb else ["парк", "достопримечательность", "развлечения", "музей", "галерея", "тц"]
if st.button("Найти приключения!", type="primary", use_container_width=True, key="lucky_btn"):
    pool = retrieve("", lat, lon, 100.0 if anywhere else radius, k=40, now=base_now, categories=cats or None, min_rating=min_rating, only_rated=True,
                    group=group_n, here=here_keys, weather_bad=wb, nodist=anywhere)
    if gems:
        pool = [p for p in pool if "Скрытая жемчужина" in tags_for(p["id"])]
    if not pool:
        st.warning("В радиусе нет подходящих мест — увеличьте радиус.")
    else:
        pick = random.choices(pool, weights=[max(p["score"], .05) ** 3 for p in pool])[0]
        ph, names = st.empty(), [p["name"] for p in pool]
        for i in range(16):
            ph.markdown(f"<div class='spin'>{random.choice(names)}</div>", unsafe_allow_html=True)
            time.sleep(0.05 + i * 0.012)
        ph.markdown(f"<div class='spin win'>{pick['name']}</div>", unsafe_allow_html=True)
        time.sleep(0.6)
        ss.query, ss.show_all, ss.selected, ss.map_last, ss.lucky = "", True, pick["id"], None, pick["id"]
        ss.show_sig, ss.browse_sig = ("", tuple(cats)), (tuple(cats), True, False)  # чтобы выбор рулетки не сбрасывался
        ss.mv["map"] = ("target", ss.mv.get("map", ("all", 0))[1] + 1)
        ss.scroll_to_map = True
        st.rerun()
MINI_STAY = {"кофейня": 40, "парк": 45, "галерея": 45, "музей": 60, "тц": 45, "достопримечательность": 30, "ресторан": 70, "бар": 60}  # на 3 часа
MINI_SLOTS = [("кофейня",), ("парк", "галерея", "музей", "тц", "достопримечательность"), ("ресторан", "бар")]  # кофе → прогулка/культура → ужин
if st.button("Составить мини-маршрут на 3 часа", use_container_width=True, key="mini_btn"):
    _first = retrieve("", lat, lon, 100.0 if anywhere else radius, k=10, now=base_now, categories=list(MINI_SLOTS[0]), only_rated=True, group=1,
                      here=here_keys, nodist=anywhere)
    _pick, _walks, _used = [], [], 0
    random.shuffle(_first)  # повторное нажатие даёт другой маршрут из тех же лучших мест
    for _f in _first:  # пробуем несколько стартовых мест и берём цепочку, где больше всего точек
        _ch, _wk, _us, _cur = [_f], [0], MINI_STAY.get(_f["category"], 40), (_f["lat"], _f["lon"])
        for _cats in MINI_SLOTS[1:]:
            for _c in retrieve("", _cur[0], _cur[1], 2.0, k=15, now=base_now, categories=list(_cats), only_rated=True, group=1, here=()):
                if any(haversine_km(_c["lat"], _c["lon"], q["lat"], q["lon"]) < 0.12 for q in _ch) or _c["category"] in {q["category"] for q in _ch}:
                    continue  # то же здание или категория, которая уже есть в маршруте, — пропускаем
                _w = round(haversine_km(_cur[0], _cur[1], _c["lat"], _c["lon"]) / 4.5 * 60)
                _s = MINI_STAY.get(_c["category"], 40)
                if _us + _w + _s <= 185:
                    _ch.append(_c); _wk.append(_w); _us += _w + _s; _cur = (_c["lat"], _c["lon"])
                    break
        if len(_ch) > len(_pick):
            _pick, _walks, _used = _ch, _wk, _us
        if len(_pick) == len(MINI_SLOTS):
            break
    if len(_pick) < 2:
        st.warning("Не удалось собрать маршрут на 3 часа рядом — выберите место в «Параметрах» или увеличьте радиус.")
    else:
        _t0 = base_now.replace(second=0, microsecond=0) + timedelta(minutes=(15 - base_now.minute % 15) % 15)
        ss.mini = dict(ids=[c["id"] for c in _pick], walks=_walks, t0=_t0.hour * 60 + _t0.minute, total=_used)
        ss.route = list(ss.mini["ids"])
        st.balloons()
        st.rerun()
if ss.get("mini"):
    _m = ss.mini
    _t, _rows = _m["t0"], ""
    for _n, (_i, _w) in enumerate(zip(_m["ids"], _m["walks"]), 1):
        _p = BY_ID[_i]
        _t += _w
        _stay = MINI_STAY.get(_p["category"], 40)
        _walk = f"<div class='mwalk'>↓ {_w} мин пешком</div>" if _w else ""
        _rows += (f"{_walk}<div class='ms'><div class='mtime'>{_t // 60 % 24:02d}:{_t % 60:02d}</div><div class='mdot'>{_n}</div><div class='mbody'>"
                  f"<b>{_p['name']}</b><span>{CAT_LABEL.get(_p['category'], _p['category'])} · ~{_stay} мин"
                  + (f" · ★ {_p['rating']}" if _p.get("rating") else "") + f"</span><em>{SHORT_DO.get(_p['category'], 'Загляните и оцените на месте')} <small class='src idea'>идея</small></em></div></div>")
        _t += _stay
    st.markdown(f"<div class='mini'><div class='mk'>🧭 Мини-маршрут на 3 часа</div><div class='mt'>{len(_m['ids'])} места · около {_m['total']} мин"
                f"</div><div class='msteps'>{_rows}</div><div class='mnote'>Места и оценки — данные POI (OpenStreetMap + 2GIS); порядок, время и подсказки — идея. Время — ориентир.</div></div>",
                unsafe_allow_html=True)
    if st.button("Скрыть мини-маршрут", key="mini_hide"):
        ss.mini = None
        st.rerun()
winner_slot = st.container()  # сюда после «Найти приключения!» выводится выпавшее место — прямо под кнопкой, на главном экране
if ss.get("evening"):
    ev = ss.evening
    if ev["variants"]:
        with st.container(border=True):
            st.markdown("<div class='panel-t'>Варианты вечера</div><div class='meta'>Выберите вариант — маршрут построится сам.</div>", unsafe_allow_html=True)
            titles = [v["title"] for v in ev["variants"]]
            anim, prev = ss.pop("ev_anim", False), ss.get("ev_pick") or titles[0]  # анимация всплытия — только после сборки
            st.markdown("<div class='vgrid'>" + "".join(
                f"<div class='vcard{' pop' if anim else ''}{' sel' if v['title'] == prev else ''}' style='animation-delay:{i * 0.22:.2f}s'>"
                f"<b>{v['title']}</b><span>{' → '.join(v['names'])}</span></div>" for i, v in enumerate(ev["variants"])) + "</div>", unsafe_allow_html=True)
            ch = st.segmented_control("Вариант", titles, default=titles[0], key="ev_pick", label_visibility="collapsed") or titles[0]
            v = ev["variants"][titles.index(ch)]
            if ss.get("ev_applied") != ch:
                ss.route, ss.ev_applied = list(v["ids"]), ch
            st.markdown("<div class='evening' style='box-shadow:none'>" + "".join(f"<div class='row'>{l}</div>" for l in v["lines"])
                        + (f"<div class='row' style='margin-top:8px; color:#CFD7E8'>{v['story']}</div>" if v.get("story") else "")
                        + "<div class='meta' style='margin-top:6px'><span class='src idea'>Идея</span> места из базы</div></div>", unsafe_allow_html=True)
            if st.button("Скрыть варианты", key="evening_hide"):
                ss.evening = None
                st.rerun()
    else:
        st.warning("Для вечера не нашлось мест в радиусе — увеличьте радиус.")

scen = BY_LABEL.get(ss.query) if not ss.show_all else None
sim_now, fmt_cats, access_all = None, None, False
if scen and scen["key"] == "birthday":
    k = scen["key"]
    with st.container(border=(k != "view")):  # у «вида на город» панели нет
        if k != "view":
            st.markdown(f"<div class='panel-t'>{scen['title']}</div>", unsafe_allow_html=True)
        if k == "view":
            pass  # у «вида на город» дополнительных элементов нет
        elif k == "adrenaline":
            lvl = st.slider("Уровень адреналина", 1, 5, 3, key="adr_lvl")
            st.markdown(f"**{lvl}/5 — {LEVELS[lvl]}**")
            if st.button("Случайный челлендж для компании", key="chal_btn"):
                ss.chal = random.choice(CHALLENGES)
            if ss.get("chal"):
                st.markdown(f"<div class='blurb story'>{ss.chal}</div>", unsafe_allow_html=True)
        elif k == "dog":
            size = st.segmented_control("Питомец", ["Маленькая", "Средняя", "Крупная"], default="Средняя", key="dog_size") or "Средняя"
            st.markdown(DOG_TIPS[size])
            got = [st.checkbox(t, key=f"dog_chk_{i}") for i, t in enumerate(DOG_CHECKLIST)]
            st.progress(sum(got) / len(got), text=f"Собрано {sum(got)} из {len(got)}" + (" — можно выходить!" if all(got) else ""))
        elif k == "birthday":
            fmt = st.segmented_control("Формат праздника", list(FORMATS), default="Ужин", key="bd_fmt") or "Ужин"
            fmt_cats = FORMATS[fmt]
            st.markdown(f"{FORMAT_HINT[fmt]}. Гостей: **{group_n}** (меняется в «Параметрах» → «Дополнительно»).")
if ss.pop("fire_balloons", False):  # шарики при каждом включении «Отпраздновать день рождения»
    st.balloons()
_fx = ss.pop("fx", None)
if _fx == "dog":  # лапки шагают по экрану при включении «с собакой»
    _items = "".join(f"<span class='fxi paw' style='left:{6 + i * 7.1:.1f}%; bottom:{12 + (i * 29) % 62}%; animation-delay:{i * .15:.2f}s; "
                     f"rotate:{25 if i % 2 else -25}deg'>🐾</span>" for i in range(13))
elif _fx == "adrenaline":  # молнии бьют по экрану при включении «адреналина»
    _items = "<span class='fxflash'></span>" + "".join(
        f"<span class='fxi bolt' style='left:{4 + (i * 53) % 90}%; top:{6 + (i * 37) % 70}%; animation-delay:{(i % 6) * .18:.2f}s; "
        f"font-size:{2.6 + (i % 3) * 1.1:.1f}rem'>⚡</span>" for i in range(12))
else:
    _items = ""
if _items:
    st.markdown("<style>.fxw{position:fixed; inset:0; z-index:9999; pointer-events:none; overflow:hidden;}"
                ".fxi{position:absolute; opacity:0; line-height:1;}"
                ".paw{font-size:3rem; filter:drop-shadow(0 0 12px rgba(212,175,55,.8)); animation:paw 2.4s ease-out both;}"
                ".bolt{filter:drop-shadow(0 0 16px rgba(255,214,0,.95)); animation:bolt 1.4s ease-out both;}"
                ".fxflash{position:absolute; inset:0; background:radial-gradient(circle at 50% 40%, rgba(255,240,170,.55), transparent 65%); opacity:0; animation:flash 1.1s ease-out both;}"
                "@keyframes paw{0%{opacity:0; scale:.4;} 18%{opacity:1; scale:1.15;} 70%{opacity:.9; scale:1;} 100%{opacity:0; scale:.9;}}"
                "@keyframes bolt{0%{opacity:0; scale:.3;} 12%{opacity:1; scale:1.25;} 24%{opacity:.2;} 36%{opacity:1; scale:1;} 100%{opacity:0; scale:1.1;}}"
                "@keyframes flash{0%{opacity:0;} 10%{opacity:1;} 25%{opacity:.15;} 40%{opacity:.8;} 100%{opacity:0;}}"
                "@media (prefers-reduced-motion: reduce){.fxw{display:none;}}</style>"
                f"<div class='fxw'>{_items}</div>", unsafe_allow_html=True)
with search_slot, st.form("search", border=False):
    fc1, fc2 = st.columns([6, 1], vertical_alignment="bottom")
    typed = fc1.text_input("Что хочется?", value="", placeholder="Например: тихая кофейня с розеткой или где потусить с друзьями")
    go = fc2.form_submit_button("Найти", use_container_width=True)
if go and typed.strip():
    ss.query, ss.selected, ss.show_all, ss.scen_browse = typed.strip(), None, False, False

now = sim_now or base_now
if ss.get("show_sig") != (ss.query, tuple(cats)):  # сменили запрос или категории — «Все места» выключаем
    ss.show_all, ss.show_sig = False, (ss.query, tuple(cats))
radius_eff = 100.0 if anywhere else radius  # «Другое» без ввода: радиуса нет
if mode == "lrt":  # на ЛРТ можно доехать из любой точки города — радиус не ограничиваем
    radius_eff = 100.0
if scen and scen["key"] == "dog":  # мест с собакой в базе мало — ищем по всему городу, ближайшие первыми
    radius_eff = 100.0
show_all_eff = ss.show_all or (anywhere and not ss.query and not cats)  # ничего не вводили — выходят все заведения
if ss.show_all:  # «Все места» — весь город, а не только радиус
    radius_eff = 100.0
scen_browse = bool(ss.scen_browse and scen and not ss.show_all)
browse = (not ss.query and bool(cats)) or show_all_eff or access_all or scen_browse  # категории без запроса или «Все места»: показываем всё, выбираете вы
all_cats = browse and (show_all_eff or access_all or scen_browse or set(cats) == set(_cnt))  # выбраны все категории / «Все места» — «лучшего выбора» нет
res = retrieve("" if (show_all_eff or access_all) else ss.query, lat, lon, radius_eff, k=60 if browse else top_k, now=now, categories=cats or (list(fmt_cats) if fmt_cats else None),
               min_rating=min_rating, only_rated=only_rated, group=group_n, here=here_keys,
               weather_bad=weather_bad and not (scen and scen["key"] == "dog"), nodist=anywhere)
if access_all and scen:
    for _r in res:
        _r["criteria"] = assess(scen["label"], _r)
for _r in res:
    _r["ui_tags"] = tags_for(_r["id"])
if mode == "lrt":  # только места рядом со станцией ЛРТ (до 500 м пешком)
    res = [r for r in res if "Рядом ЛРТ" in r["ui_tags"]]
if gems:
    res = [r for r in res if "Скрытая жемчужина" in r["ui_tags"]]
tag_sel = []
best_id = res[0]["id"] if res else None
by_score = list(res)
if sort == "Ближе":
    res = sorted(res, key=lambda x: x["dist_km"])
elif sort == "Рейтинг":
    res = sorted(res, key=lambda x: -(x["rating"] or 0))


def stars(r):
    return f"{'★' * round(r)}{'☆' * (5 - round(r))} {r}"


def quality_pill(p):
    cls = {"green": "good", "orange": "mid", "red": "bad", "gray": "none"}[p["quality_color"]]
    return f"<span class='pill {cls}'>{BADGE[p['quality_color']]} {p['quality_label']}</span>"


def taxi_link(p):
    return (f"https://3.redirect.appmetrica.yandex.com/route?start-lat={lat}&start-lon={lon}&end-lat={p['lat']}&end-lon={p['lon']}"
            "&appmetrica_tracking_id=1178268795219780156")


def twogis_link(p):
    """Карточка/поиск места в 2GIS, карта центрируется на координатах места."""
    return f"https://2gis.kz/astana/search/{quote(p['name'])}?m={p['lon']}%2C{p['lat']}%2F17"


def hours_html(p):
    t1, t2 = hours_note(p)
    if t2:  # часов нет — только вероятность, без «открыто/закрыто»
        return f"<span style='color:var(--muted); font-size:.88rem'>Часы не указаны · {t2}</span>"
    return f"<span style='color:var(--muted); font-size:.88rem'>Часы: {t1}</span>"


def match_html(p, short=False):
    """Коротко: от какой локации расстояние и какие критерии, фильтры и теги совпали у места."""
    q = "" if ss.show_all else ss.query
    crit = assess(q, p) if q else []
    bits = [] if anywhere else [f"{p['dist_km']} км от «{start_name}»"]
    if cats:
        bits.append("категория: " + CAT_LABEL.get(p["category"], p["category"]).lower())
    for lab, v, note in crit:
        bits.append(f"{lab}: {note if v else 'нет данных'}")
    if tag_sel and not short:
        bits.append("теги: " + ", ".join(tag_sel))
    return f"<div class='meta'><b>Совпало:</b> {' · '.join(bits)}</div>"


def data_block(p):
    """Теги, фильтры (с локацией) и источник — под блоком «Лучший выбор»."""
    flt = (["по всему городу"] if (anywhere or radius_eff >= 100) else [f"от «{start_name}»", f"радиус {radius} км"]) + ([f"категории: {', '.join(CAT_LABEL.get(c, c).lower() for c in cats)}"] if cats else []) + (["у станций ЛРТ (до 500 м)"] if mode == "lrt" else []) \
        + ([f"теги: {', '.join(tag_sel)}"] if tag_sel else []) + ([f"компания {group_n} чел."] if group_n > 1 else []) + [MODES[mode].lower()]
    rows = []
    if p:
        rows.append(f"<div><span class='l'>Теги</span><span>{chips_html(p, 12)}</span></div>")
    rows.append(f"<div><span class='l'>Фильтры</span><span>{'; '.join(flt)}</span></div>")
    rows.append(f"<div><span class='l'>Источник</span><span>{source_line(p, True).replace('Источник: ', '') if p else 'OpenStreetMap, 2GIS'}</span></div>")
    return "<div class='dgrid'>" + "".join(rows) + "</div>"


def blurb_html(p, story):
    label = "Сгенерировано по данным POI" if story else "Данные POI"
    cls = "idea" if story else "data"
    return f"<div class='blurb{' story' if story else ''}'><span class='src {cls}'>{label}</span> {blurb(p)}</div>"


def chips_html(p, n=5):
    return "".join(f"<span class='chip'>{t}</span>" for t in (p.get("ui_tags") or tags_for(p["id"]))[:n])


def _old_chips_html(p):
    return "".join(f"<span class='chip'>{label}</span>" for tag, label in BADGES.items() if tag in p["tags"])


def lrt_line(p):
    s = nearest_stop("lrt", p["lat"], p["lon"])
    return f"<div class='meta'>ЛРТ: станция «{s[0]}» в {s[1]} м</div>" if s else ""


def tags_html(p, n=6):
    return "".join(f"<span class='pill tag'>{t}</span>" for t in p["tags"][:n])


def _icon(bg, kind):
    glyph = {"bus": "<rect x='18' y='16' width='28' height='26' rx='5' fill='white'/><rect x='21' y='20' width='22' height='9' rx='2' fill='%s'/>"
                    "<circle cx='25' cy='46' r='3' fill='white'/><circle cx='39' cy='46' r='3' fill='white'/>" % bg,
             "lrt": "<rect x='19' y='14' width='26' height='30' rx='7' fill='white'/><rect x='23' y='19' width='18' height='10' rx='2' fill='%s'/>"
                    "<circle cx='26' cy='35' r='2.5' fill='%s'/><circle cx='38' cy='35' r='2.5' fill='%s'/>"
                    "<path d='M22 49 L28 44 M42 49 L36 44' stroke='white' stroke-width='3' stroke-linecap='round'/>" % (bg, bg, bg)}[kind]
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64' viewBox='0 0 64 64'><circle cx='32' cy='32' r='30' fill='%s' "
           "stroke='white' stroke-width='4'/>%s</svg>" % (bg, glyph))
    return dict(url="data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(), width=64, height=64, anchorY=32)


ICONS = {"bus": _icon("#FF8C00", "bus"), "lrt": _icon("#1FB6E8", "lrt")}
SEG_STYLE = {"walk": ([235, 235, 235, 110], 2), "bus": ([255, 140, 0, 250], 7), "lrt": ([30, 190, 255, 250], 8)}


def fit_view(coords, width_px=700, height_px=500):
    """Центр и масштаб карты так, чтобы в кадр попали все точки (и вы)."""
    lats, lons = [c[0] for c in coords], [c[1] for c in coords]
    clat, clon = (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2
    lon_span = max(max(lons) - min(lons), 0.004) * 1.35
    lat_span = max(max(lats) - min(lats), 0.004) * 1.45
    zoom_lon = math.log2(width_px / 256 * 360 / lon_span)
    zoom_lat = math.log2(height_px / 256 * 360 * math.cos(math.radians(clat)) / lat_span)
    return pdk.ViewState(latitude=clat, longitude=clon, zoom=max(9.5, min(15.5, min(zoom_lon, zoom_lat))))


def map_controls(key, focus_ok=True, fallback_id=None):
    """Кнопки возврата вида карты: все места / выбранное / я здесь. «К выбранному» работает всегда:
    если ничего не выбрано, берём лучшее место из выдачи."""
    c1, c2, c3 = st.columns(3)
    for col, label, mode in ((c1, "Все места", "all"), (c2, "К выбранному", "target"), (c3, "Я здесь", "me")):
        if col.button(label, key=f"mc_{key}_{mode}", use_container_width=True):
            if mode == "target" and key == "map" and not focus_ok:
                if fallback_id is None:
                    st.toast("Пока нечего показывать — выберите сценарий или запрос.", icon="ℹ️")
                    st.rerun()
                ss.selected = fallback_id  # ничего не выбрано — наводим на лучшее место
            ss.mv[key] = (mode, ss.mv.get(key, ("all", 0))[1] + 1)
            if key == "map":
                ss.map_last = None
            if mode == "all" and key == "map":
                if ss.query in BY_LABEL and not ss.show_all:  # внутри сценария: все места, которые предлагает этот сценарий
                    ss.scen_browse, ss.selected = True, None
                else:
                    ss.show_all, ss.selected = True, None  # «Все места» — на карте и в списке показываем все места в радиусе
            st.rerun()


def draw_map(points, selected_id=None, best=None, path=None, numbered=None, key="map", focus=None, segments=None, stops=None):
    data = []
    for n, p in enumerate(points):
        emoji, color = GROUP[p["group"]]
        label = (p["name"] if not numbered else f"{numbered[p['id']]}. {p['name']}").replace("'", "’")
        data.append(dict(name=label, lat=p["lat"], lon=p["lon"], id=p["id"], color=color + [235],
                         r=75 if p["id"] in (selected_id, best) else 40,
                         off=[0, -16] if n % 2 == 0 else [0, 16]))  # подписи чередуем сверху/снизу, чтобы не слипались
    me = [dict(name="Вы здесь", lat=lat, lon=lon, color=[255, 255, 255, 255], r=50, off=[0, -16])]
    layers = []
    ride_labels = []
    if segments:  # автобус / ЛРТ: пешие участки тонко и бледно, транспорт — толстая цветная линия с белой подложкой и подписью
        for kind in ("walk", "bus", "lrt"):
            segs = [dict(a=sg["path"][k], b=sg["path"][k + 1]) for sg in segments if sg["kind"] == kind for k in range(len(sg["path"]) - 1)]
            if segs:
                col, w = SEG_STYLE[kind]
                if kind != "walk":
                    layers.append(pdk.Layer("LineLayer", segs, get_source_position="a", get_target_position="b", get_width=w + 5,
                                            get_color=[255, 255, 255, 230]))
                layers.append(pdk.Layer("LineLayer", segs, get_source_position="a", get_target_position="b", get_width=w, get_color=col))
        for sg in segments:
            if sg["kind"] in ("bus", "lrt") and len(sg["path"]) > 1:
                mid = sg["path"][len(sg["path"]) // 2]
                ride_labels.append(dict(lon=mid[0], lat=mid[1], label="ЛРТ" if sg["kind"] == "lrt" else "Автобус"))
    elif path:
        segs = [dict(a=path[k], b=path[k + 1]) for k in range(len(path) - 1)]
        layers.append(pdk.Layer("LineLayer", segs, get_source_position="a", get_target_position="b",
                                get_width=4, get_color=[212, 175, 55, 235]))
    stop_rows = []
    for s in stops or []:
        word = "Станция" if s["kind"] == "lrt" else "Остановка"
        stop_rows.append(dict(lat=s["lat"], lon=s["lon"], icon=ICONS[s["kind"]], sz=34 if s["major"] else 20, rad=11 if s["major"] else 6,
                              label=f"{word} «{s['name']}»" if s["major"] else "", color=[255, 140, 0, 255] if s["kind"] == "bus" else [31, 182, 232, 255]))
    chars = "".join(sorted({ch for d in data + me for ch in d["name"]} | {ch for r in stop_rows for ch in r["label"]} | set(" .,-0123456789«»ЛРТАвтобус")))  # кириллица и др. символы подписей
    if ride_labels:
        layers.append(pdk.Layer("TextLayer", ride_labels, get_position="[lon, lat]", get_text="label", get_size=14,
                                get_color=[255, 255, 255], get_pixel_offset=[0, 0], background=True, character_set="'" + chars + "'",
                                font_family="'Arial'", font_weight=700, get_background_color=[20, 140, 200, 245], background_padding=[7, 3]))
    if stop_rows:
        layers += [pdk.Layer("ScatterplotLayer", stop_rows, get_position="[lon, lat]", get_fill_color="color", get_radius="rad",
                             radius_units="pixels", get_line_color=[255, 255, 255, 255], stroked=True, line_width_min_pixels=2,
                             get_line_width=1, radius_scale=1, radius_min_pixels=5, radius_max_pixels=14),
                   pdk.Layer("IconLayer", stop_rows, get_icon="icon", get_position="[lon, lat]", get_size="sz", size_units="pixels"),
                   pdk.Layer("TextLayer", [r for r in stop_rows if r["label"]], get_position="[lon, lat]", get_text="label", get_size=12,
                             get_color=[255, 255, 255], get_pixel_offset=[0, 30], background=True, character_set="'" + chars + "'",
                             font_family="'Arial'", font_weight=600, get_background_color=[6, 14, 36, 235], background_padding=[4, 2])]
    layers += [
        pdk.Layer("ScatterplotLayer", data, get_position="[lon, lat]", get_fill_color=[255, 215, 0, 60], get_radius="r",
                  radius_min_pixels=12, radius_max_pixels=26, stroked=False),
        pdk.Layer("ScatterplotLayer", data, id="places", get_position="[lon, lat]", get_fill_color="color",
                  get_radius="r", radius_min_pixels=4, radius_max_pixels=10, pickable=True, stroked=True,
                  get_line_color=[255, 255, 255], line_width_min_pixels=2),
        pdk.Layer("ScatterplotLayer", me, get_position="[lon, lat]", get_fill_color="color", get_radius="r",
                  radius_min_pixels=5, radius_max_pixels=9),
        pdk.Layer("TextLayer", data + me, get_position="[lon, lat]", get_text="name", get_size=13,
                  get_color=[237, 233, 221], get_pixel_offset="off", background=True, character_set="'" + chars + "'",
                  font_family="'Arial'", font_weight=600,
                  get_background_color=[6, 14, 36, 230], background_padding=[4, 2]),
    ]
    mode, nonce = ss.mv.get(key, ("all", 0))
    if mode == "target" and focus:
        view = pdk.ViewState(latitude=focus[0], longitude=focus[1], zoom=15)
    elif mode == "me":
        view = pdk.ViewState(latitude=lat, longitude=lon, zoom=14)
    else:
        view = fit_view([(p["lat"], p["lon"]) for p in points] + [(lat, lon)] + [(r["lat"], r["lon"]) for r in stop_rows])
    view.min_zoom, view.max_zoom = 9, 18
    d = pdk.Deck(layers=layers, initial_view_state=view, map_provider="carto", map_style=pdk.map_styles.CARTO_DARK,
                 tooltip={"text": "{name}"})
    return st.pydeck_chart(d, on_select="rerun", selection_mode="single-object", key=f"{key}{nonce}", height=500)


@st.cache_data(show_spinner=False, ttl=3600)
def cached_route(mode, pts):
    return get_route(mode, list(pts))


def show_legs(route, names):
    if route.get("note"):
        st.info(route["note"])
    elif route["approx"]:
        st.warning("Сервис маршрутов недоступен — показана прямая линия и грубая оценка времени.")
    for i, leg in enumerate(route["legs"]):
        with st.expander(f"**{i + 1}. {names[i]} → {names[i + 1]}** · {fmt_dist(leg['distance'])} · "
                         f"{max(1, round(leg['duration'] / 60))} мин", expanded=i == 0 and len(route["legs"]) == 1):
            if not leg["steps"]:
                st.caption("Подробных подсказок нет — откройте навигатор кнопкой ниже.")
            for s in leg["steps"]:
                st.markdown(f"<div class='step'>{s['text']} <span style='color:#888'>· {fmt_dist(s['distance'])}"
                            f"</span></div>" if s["distance"] else f"<div class='step'>🏁 {s['text']}</div>",
                            unsafe_allow_html=True)


PHOTOS = {"Kök Grand View": ["assets/photos/kok_53.jpg", "assets/photos/kok_54.jpg", "assets/photos/kok_55.jpg"],
          "Mokki": ["assets/photos/mokki_56.jpg", "assets/photos/mokki_57.jpg"],
          "Точка Bistro": ["assets/photos/tochka_58.jpg", "assets/photos/tochka_59.jpg", "assets/photos/tochka_60.jpg"],
          "Бату Донер": ["assets/photos/batu_64.jpg", "assets/photos/batu_65.jpg"],
          "Керуен": ["assets/photos/keruen_67.jpg", "assets/photos/keruen_68.jpg"],
          "Ботанический сад": ["assets/photos/garden_69.jpg", "assets/photos/garden_70.jpg", "assets/photos/garden_71.jpg"],
          "Ailand": ["assets/photos/ailand_72.jpg", "assets/photos/ailand_73.jpg"],
          "Fire Drift": ["assets/photos/fire_74.jpg", "assets/photos/fire_75.jpg", "assets/photos/fire_76.jpg"],
          "Хан Шатыр": ["assets/photos/khan_77.jpg"],
          "Turandot": ["assets/photos/turandot_78.jpg", "assets/photos/turandot_79.jpg"],
          "Площадка для выгула собак": ["assets/photos/dogpark_80.jpg"],
          "Chaplin Cinemas": ["assets/photos/chaplin_81.jpg", "assets/photos/chaplin_82.jpg", "assets/photos/chaplin_83.jpg"]}  # фото предоставила команда


def show_photos(p):
    """Фото места (если есть): ряд из трёх кадров."""
    _root = os.path.dirname(os.path.abspath(__file__))  # пути к фото не зависят от того, откуда запущен сайт (важно для Windows)
    files = [os.path.join(_root, f) for f in PHOTOS.get(p["name"], []) if os.path.exists(os.path.join(_root, f))]
    if files:
        for col, f in zip(st.columns(len(files)), files):
            col.image(f, width="stretch")


def details(p, scope="m", photos=True):
    with st.container(border=True):
        if photos:
            show_photos(p)
        st.subheader(p["name"])
        st.markdown(f"<div class='meta'>{'' if anywhere else str(p['dist_km']) + ' км · '}{p['address'] or 'адрес не указан'}</div>", unsafe_allow_html=True)
        st.markdown(hours_html(p), unsafe_allow_html=True)
        st.markdown(blurb_html(p, p["name"] in STORIES), unsafe_allow_html=True)
        c = st.columns(3)
        c[0].link_button("2GIS", twogis_link(p), use_container_width=True)
        c[1].link_button("Google Maps", f"https://www.google.com/maps/search/?api=1&query={p['lat']},{p['lon']}", use_container_width=True)
        c[2].link_button("Такси", taxi_link(p), use_container_width=True)


slot_shown_id = None
if ss.get("selected") is not None and (browse or ss.selected != best_id) and ss.selected in BY_ID:
    slot_shown_id = ss.selected  # выбранное место (из списка, с карты или рулеткой) выводим наверх, на главный экран
    with winner_slot:
        st.markdown(f"<div class='winner-k'>{'🎲 Вам выпало' if ss.get('lucky') == ss.selected else '📍 Вы выбрали'}</div>", unsafe_allow_html=True)
        details(get_place(ss.selected, lat, lon, now, here_keys))


def way_html(route, dest_ids, title=None):
    """Понятное объяснение, как быстрее дойти: шаги с ориентирами и заведения, мимо которых пройдёте."""
    mins = max(1, round(route["duration"] / 60))
    head = f"<b>{title or 'Как дойти'}</b> · {fmt_dist(route['distance'])} · {mins} мин"
    steps = []
    for leg in route["legs"]:
        steps += clean_steps(leg)
    rows = ""
    for n, s in enumerate(steps, 1):
        mark = ""
        if s.get("loc"):
            near_p = min((p for p in POIS if p["id"] not in dest_ids),
                         key=lambda p: haversine_km(s["loc"][1], s["loc"][0], p["lat"], p["lon"]), default=None)
            if near_p and haversine_km(s["loc"][1], s["loc"][0], near_p["lat"], near_p["lon"]) <= 0.08:
                mark = f" (у «{near_p['name']}»)"
        direction = f" — {compass(s['bearing'])}" if s.get("bearing") is not None else ""
        go = f", идите {fmt_dist(s['distance'])}" if s["distance"] and not s["text"].startswith(("Дойдите", "Проедьте")) else (f" · {fmt_dist(s['distance'])}" if s["distance"] else "")
        rows += f"<div class='step'>{n}. {s['text']}{mark}{direction}{go}</div>"
    paths = [sg["path"] for sg in route["segments"] if sg["kind"] == "walk"] if route.get("segments") else [route["path"]]
    near = [(n, m) for n, m in places_along(paths, POIS, exclude_ids=dest_ids, max_m=70) if m >= 30]
    passing = ""
    if near:
        passing = "<div class='step'><b>Пройдёте мимо:</b> " + ", ".join(f"{n} (через {fmt_dist(m)})" for n, m in near[:5]) + "</div>"
    note = f"<div class='meta'>{route['note']}</div>" if route.get("note") else ""
    return f"<div class='way'>{head}{rows}{passing}{note}</div>"


def route_preview(target):
    """Путь до выбранного места строится сразу и рисуется на карте (без текстовой строки над картой)."""
    return cached_route(mode, ((lat, lon), (target["lat"], target["lon"])))


if not ss.query and not cats and not show_all_eff:
    st.markdown("<div class='meta' style='text-align:center; padding:26px 0'>Выберите сценарий выше, опишите запрос или выберите категории в «Параметрах».</div>", unsafe_allow_html=True)
elif not res:
    _q = "" if ss.show_all else ss.query
    _kw = dict(now=now, categories=cats or (list(fmt_cats) if fmt_cats else None), min_rating=min_rating, only_rated=True, group=group_n)
    near = retrieve(_q, lat, lon, 15.0, k=1, here=here_keys, **_kw)
    where = [n for n, (la, lo) in START.items() if n != start_name and retrieve(_q, la, lo, 2.0, k=1, here=START_INFO[n][1], **_kw)]
    st.warning(("Скрытых жемчужин в радиусе нет — выключите «Без туристов». " if gems else "")
               + ("Подходящих мест нет — попробуйте убрать фильтры." if radius_eff >= 100 else f"В радиусе {radius} км от «{start_name}» подходящих мест нет.")
               + (f" Ближайшее: {near[0]['name']}, {near[0]['dist_km']} км." if near else "")
               + (f" Места есть возле: {', '.join(where)}." if where else ""))
else:
    top = next(r for r in res if r["id"] == best_id)
    if browse and ss.get("browse_sig") != (tuple(cats), ss.show_all, scen_browse):  # сменили категории — выбор места сбрасываем
        ss.selected, ss.browse_sig = None, (tuple(cats), ss.show_all, scen_browse)
    # в режиме «только категории» место не выбирается само: сначала выбираете вы, потом описание
    target = next((r for r in res if r["id"] == ss.selected), None if browse else top)
    left, right = st.columns([1, 1.25])
    with left:
        if all_cats:
            st.markdown(f"<div class='best'><div class='k'>Все места</div><div class='meta'>{len(res)} мест{' по сценарию «' + scen['label'] + '»' if scen_browse else ' рядом'} — выберите любое на карте или в списке</div></div>"
                        + (f"<div class='fit'>Рулетка выбрала: <b>{BY_ID[ss.lucky]['name']}</b></div>" if ss.get("lucky") and ss.get("lucky") == ss.selected else ""), unsafe_allow_html=True)
            st.markdown(data_block(target), unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='best'><div class='k'>Лучший выбор</div><div class='n'>{top['name']}</div>"
                        + ("" if anywhere else f"<span class='acc'>{top['dist_km']} км</span> · ")
                        + (f"<span class='stat'>★ {top['rating']}</span> · {top['reviews']} оценок" if top["rating"] else "") + "</div>", unsafe_allow_html=True)
            st.markdown(data_block(top), unsafe_allow_html=True)
            show_photos(top)
            ck = (ss.query or tuple(cats), minutes, group_n, anywhere, tuple(r["id"] for r in by_score))
            if ck not in ss.answers:
                with st.spinner("Пишу рекомендацию…"):
                    ss.answers[ck] = generate(ss.query or "Подборка мест по выбранным категориям", minutes, by_score, now, group_n, anywhere)
            _rec, _seen2 = [], []  # те же 3 места, что названы в рекомендации (без соседей из одного здания)
            for _r in by_score:
                if all(haversine_km(_r["lat"], _r["lon"], s["lat"], s["lon"]) >= 0.12 for s in _seen2):
                    _seen2.append(_r); _rec.append(_r)
                if len(_rec) == 3:
                    break
            _ans, _mode = ss.answers[ck]
            n_rated = sum(1 for p in POIS if p["rating"])
            if _mode == "llm":
                _chips, _txt = ["AI Recommendation", "RAG · POI Database", "Gemini"], "Сгенерировано AI на основе реальных данных POI — места и факты берутся из базы, не из памяти модели."
            else:
                _chips, _txt = ["Recommendation", "RAG · POI Database"], "Места найдены по реальной базе POI (OpenStreetMap + 2GIS), текст собран по найденным данным — без выдумок нейросети."
            st.markdown("<div class='srcbar'>" + "".join(f"<span class='sb'>{c}</span>" for c in _chips)
                        + f"<span class='st'>{_txt} В базе {len(POIS)} мест, у {n_rated} есть оценка 2GIS.</span></div>", unsafe_allow_html=True)
            _parts = re.split(r"(?=<div class='rec'>)", _ans)
            if len(_parts) - 1 == len(_rec):  # карточка места и сразу под ней раскрывающееся «Подробнее» (описание, часы, фото)
                if _parts[0].strip():
                    st.markdown(_parts[0], unsafe_allow_html=True)
                for _n, (_html, _r) in enumerate(zip(_parts[1:], _rec), 1):
                    _tail = ""
                    if _n == len(_rec) and "</div>\n<div class='meta'>" in _html:  # хвост после последней карточки (напр. про бронь)
                        _html, _tail = _html.split("</div>\n<div class='meta'>", 1)
                        _html, _tail = _html + "</div>", "<div class='meta'>" + _tail
                    st.markdown(_html, unsafe_allow_html=True)
                    with st.expander(f"Подробнее о «{_r['name']}» — описание, часы, фото"):
                        details(get_place(_r["id"], lat, lon, now, here_keys), photos=_r["id"] != top["id"])  # у лучшего выбора фото уже под баннером
                    if _tail:
                        st.markdown(_tail, unsafe_allow_html=True)
            else:  # ответ в другом формате (например, от Gemini) — показываем как есть
                st.markdown(_ans, unsafe_allow_html=True)
    with right:
        rt = route_preview(target) if target else None
        ss.way_route = rt
        ev = draw_map(res, target["id"] if target else None, None if (all_cats or browse) else best_id,
                      path=rt["path"] if rt else None, focus=(target["lat"], target["lon"]) if target else None,
                      segments=rt.get("segments") if rt else None)
        map_controls("map", focus_ok=bool(target), fallback_id=(best_id if best_id is not None else (res[0]["id"] if res else None)))
        try:
            objs = ev.selection.objects.get("places", [])
            cur = objs[0]["id"] if objs else None
            if cur is not None and cur != ss.get("map_last"):  # новый клик по точке (старый выбор карты не перебивает «Подробнее»)
                ss.map_last, ss.selected = cur, cur
                ss.pending_open = twogis_link(BY_ID[cur])
                st.rerun()
        except Exception:
            pass
        if not target:
            st.markdown("<div class='meta'>Выберите место на карте или в списке.</div>", unsafe_allow_html=True)

    if target and target["id"] != slot_shown_id:  # выбранное место уже показано наверху — не дублируем
        details(get_place(target["id"], lat, lon, now, here_keys), photos=all_cats or target["id"] != top["id"])  # у «Лучшего выбора» фото уже показаны под баннером
    show_list = not (len(res) == 1 and target and res[0]["id"] == target["id"])  # одно место уже описано выше — список не дублируем
    if show_list:
        st.markdown("<div class='sec'>Найденные места</div>", unsafe_allow_html=True)
    for i in range(0, len(res) if show_list else 0, 3):
        for col, c in zip(st.columns(3), res[i:i + 3]):
            with col, st.container(border=True):
                st.markdown(f"<div class='kicker'>{CAT_LABEL.get(c['category'], c['category'])}</div>", unsafe_allow_html=True)
                _nm = st.button(c["name"], key=f"nm_{c['id']}", type="tertiary", help="Открыть место на главном экране")  # название кликабельно
                st.markdown((f"<span class='stat'>★ {c['rating']}</span> · {c['reviews']} оценок &nbsp;" if c["rating"] else "")
                            + quality_pill(c), unsafe_allow_html=True)
                st.markdown(f"<div class='meta'>{c['address'] or 'адрес не указан'}{'' if anywhere else ' · ' + str(c['dist_km']) + ' км'}</div>", unsafe_allow_html=True)
                st.markdown(hours_html(c), unsafe_allow_html=True)
                st.markdown(chips_html(c, 6), unsafe_allow_html=True)
                if scen and scen["key"] == "access":
                    st.markdown(lrt_line(c), unsafe_allow_html=True)

                b1, b2 = st.columns(2)
                if b1.button("Подробнее", key=f"more_{c['id']}", use_container_width=True) or _nm:
                    # место сразу выбирается: карта центрируется на нём, описание и путь появляются выше
                    ss.selected, ss.scroll_to_map, ss.map_last = c["id"], True, None
                    ss.mv["map"] = ("target", ss.mv.get("map", ("all", 0))[1] + 1)
                    st.rerun()
                inroute = c["id"] in ss.route
                if b2.button("✓ В маршруте" if inroute else "＋ В маршрут", key=f"add_{c['id']}",
                             use_container_width=True, disabled=inroute, type="secondary" if inroute else "primary"):
                    ss.route.append(c["id"])
                    st.toast(f"Добавлено: {c['name']}", icon="✅")
                    st.rerun()

if ss.route:
    st.markdown(f"<div class='sec'>Мой маршрут · {len(ss.route)}</div>", unsafe_allow_html=True)
    a, b = st.columns(2)
    if a.button("Оптимизировать порядок", use_container_width=True):
        ss.route = [p["id"] for p in order_nearest((lat, lon), [BY_ID[i] for i in ss.route])]
        st.rerun()
    if b.button("Очистить маршрут", use_container_width=True):
        ss.route = []
        st.rerun()

    pts = [BY_ID[i] for i in ss.route]
    coords = tuple([(lat, lon)] + [(p["lat"], p["lon"]) for p in pts])
    with st.spinner("Строю маршрут по дорогам…"):
        route = cached_route(mode, coords)
    stay = sum(STAY.get(p["category"], 45) for p in pts)
    total = round(route["duration"] / 60) + stay
    m1, m2 = st.columns(2)
    m1.metric("Дистанция", fmt_dist(route["distance"]))
    m2.metric(f"В пути · {MODES[mode].lower()}", f"{round(route['duration'] / 60)} мин")

    lc, rc = st.columns([1, 1.4])
    with lc:
        st.markdown("#### Порядок")
        for n, p in enumerate(pts):
            c1, c2, c3 = st.columns([6, 1, 1])
            c1.markdown(f"**{n + 1}.** {CAT_EMOJI.get(p['category'], '📍')} {p['name']}<br>"
                        f"<span style='color:#98A6C0'>{p['address'] or p['category']}</span>", unsafe_allow_html=True)
            if c2.button("↑", key=f"u{n}", disabled=n == 0):
                ss.route[n - 1], ss.route[n] = ss.route[n], ss.route[n - 1]
                st.rerun()
            if c3.button("✕", key=f"x{n}"):
                ss.route.pop(n)
                st.rerun()
        g, d = nav_links(list(coords), mode)
        st.link_button("Открыть в Google Maps", g, use_container_width=True, type="primary")
        st.link_button("Открыть в 2GIS", d, use_container_width=True)
    with rc:
        mp = [dict(p, quality_color=quality(p)[2]) for p in pts]
        _fp = BY_ID[ss.route_pick] if ss.get("route_pick") in ss.route else pts[0]  # «К выбранному»: выбранная точка маршрута или первая
        ev2 = draw_map(mp, path=route["path"], segments=route.get("segments"), numbered={p["id"]: n + 1 for n, p in enumerate(pts)}, key="routemap",
                       focus=(_fp["lat"], _fp["lon"]))
        map_controls("routemap")
        try:
            objs = ev2.selection.objects.get("places", [])
            if objs and objs[0]["id"] != ss.get("route_pick"):
                ss.pending_open = twogis_link(BY_ID[objs[0]["id"]])
            ss.route_pick = objs[0]["id"] if objs else ss.get("route_pick")
        except Exception:
            pass
    if route.get("note"):
        st.markdown(f"<div class='meta'>{route['note']}</div>", unsafe_allow_html=True)
if ss.get("route_pick") in ss.route:
    details(get_place(ss.route_pick, lat, lon, now, here_keys), scope="r")

if ss.get("pending_open"):  # клик по точке на карте -> сразу открываем 2GIS в новой вкладке
    st.iframe(f"<script>try{{window.parent.open({json.dumps(ss.pending_open)}, '_blank');}}catch(e){{}}</script>", height=1)
    ss.pending_open = None

FINDERS = {
    "scen": "d.querySelector('[class*=\"st-key-ex_\"]')",
    "search": "d.querySelector('[data-testid=\"stMain\"] [data-testid=\"stForm\"]')",
    "map": "d.querySelector('.winner-k')||d.querySelector('[data-testid=\"stDeckGlJsonChart\"]')",
    "places": "Array.from(d.querySelectorAll('.sec')).find(e=>e.textContent.includes('Найденные места'))",
    "route": "Array.from(d.querySelectorAll('.sec')).find(e=>e.textContent.includes('Мой маршрут'))",
}


def scroll_script(finder):
    """Прокрутка с повторами: страница ещё дорисовывается (карта, карточки), поэтому пробуем несколько раз."""
    return ("<script>(function(){try{const d=window.parent.document;"
            f"const find=()=>{finder};"
            "let n=0;const go=()=>{const el=find();if(el){el.scrollIntoView({behavior:n<2?'smooth':'auto',block:'start'});}"
            "if(++n<5)setTimeout(go,n<3?350:700);};setTimeout(go,250);}catch(e){}})();</script>")


if ss.get("scroll_to_map"):  # выбрали место в списке — прокручиваем страницу вверх, к карточке выбранного места
    st.iframe(scroll_script(FINDERS["map"]), height=1)
    ss.scroll_to_map = False

if ss.query or cats or ss.show_all:
  with st.expander("О данных"):
      crit = ", ".join(lab for lab, _ in concepts_in(ss.query)) or ("выбранные категории" if browse else "поиск по описанию и тегам")
      n_rated = sum(1 for p in POIS if p["rating"])
      st.markdown(
          f"- **Локация:** «{start_name}» ({start_addr}) — только для расстояний, не сохраняется.\n"
          f"- **Фильтры:** {'весь город' if radius_eff >= 100 else f'радиус {radius} км'}, компания {group_n} чел., способ: {MODES[mode].lower()}"
          f"{', категории: ' + ', '.join(CAT_LABEL.get(c, c) for c in cats) if cats else ''}.\n"
          f"- **Критерии запроса:** {crit}.\n"
          f"- **Источники:** OpenStreetMap (места, теги, часы) и 2GIS (оценки и часы, вручную; у {n_rated} из {len(POIS)} мест).\n"
          f"- **Нет данных:** критерий помечен «нет данных», часы — «не указаны». «Идея» — не из базы.")
